#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from os import path as os_path

from enigma import iPlayableService, iServiceInformation, eTimer

from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Sources.StaticText import StaticText
from Components.ServiceEventTracker import ServiceEventTracker
from Components.config import (
	config,
	ConfigSubsection,
	ConfigEnableDisable,
	getConfigListEntry,
)

from Screens.ChoiceBox import ChoiceBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen

import gettext
_ = gettext.gettext

config.plugins.ccprio = ConfigSubsection()
config.plugins.ccprio.autostart = ConfigEnableDisable(default=False)
config.plugins.ccprio.onecaid = ConfigEnableDisable(default=False)
config.plugins.ccprio.allcaid = ConfigEnableDisable(default=True)
config.plugins.ccprio.askcaid = ConfigEnableDisable(default=False)
config.plugins.ccprio.debug = ConfigEnableDisable(default=True)

PRIOLIST_P = []
ECMINFOPATH = "/tmp/ecm.info"
PRIOPATH = "/etc/CCcam.prio"
PRIOPATHBAK = "/etc/CCcam.prio.bak"
PRIOLIST_D = []
PRIOLIST_D.append("# Make with CCPrioMaker")
# PRIOLIST_D.append("I: 09C4")
PRIOLIST_D.append("P: 0D05:000000")
PRIOLIST_D.append("P: 1702:000000")
PRIOLIST_D.append("P: 1722:000000")
PRIOLIST_D.append("P: 1833:000000")
PRIOLIST_D.append("P: 0500:000000")

global CCPrioMaker_session
CCPrioMaker_session = None


def CCPrioMakerAutostart(session=None):
	global CCPrioMaker_session
	if config.plugins.ccprio.autostart.value and session:
		if CCPrioMaker_session is None:
			CCPrioMaker_session = CCPrioMaker(session)


def cleanup_r(val):
	i = val.find('#')
	if i != -1:
		val = val[:i].strip()
	k = val.find(',')
	if k != -1:
		val = val[:k].strip()
	return val


def readprio():
	if os_path.exists(PRIOPATH):
		with open(PRIOPATH, "r") as file:
			for line in file:
				if line.startswith("#"):
					continue
				line = line.upper().strip()
				if line.startswith("P:"):
					val = cleanup_r(line)
					sp = val.split(':')
					if len(sp) > 3:  # Ensure there are at least 4 elements
						PRIOLIST_P.append("%s%s" % (sp[2].strip(), sp[3].strip()))
	else:
		with open(PRIOPATH, 'w') as file:
			file.writelines(p + "\n" for p in PRIOLIST_D)


def cleanup(val):
	while val.find('\t') != -1:
		val = val.replace('\t', ' ')
	while val.find(' ') != -1:
		val = val.replace(' ', '')
	return val.strip()


def readecminfo():
	caid = ""
	provid = ""
	print(f"[CCPrioMaker] search {ECMINFOPATH}")
	try:
		with open(ECMINFOPATH, "r") as file:
			for line in file:
				line = line.strip()

				if line.startswith("caid:"):
					parts = line.split(":")
					if len(parts) == 2:
						caid = f"{int(parts[1], 16):04X}"

				elif line.startswith("provid:"):
					parts = line.split(":")
					if len(parts) == 2:
						provid = f"{int(parts[1], 16):06X}"
				if caid and provid:
					break
	except IOError as e:
		print(f"Error reading file {ECMINFOPATH}: {e}")
	return caid, provid


class CCPrioMaker(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.ssid = None
		self.valssid = ""
		self.Provider = None
		self.ServiceName = None
		self.caidlist = None
		self.ecmTimer = eTimer()
		try:
			self.hideTimer_conn = self.hideTimer.timeout.connect(self.parseEcmInfo)
		except:
			self.hideTimer.callback.append(self.parseEcmInfo)
		self.hideTimer.start(200, 1)
		self.__event_tracker = ServiceEventTracker(
			screen=self,
			eventmap={
				iPlayableService.evUpdatedEventInfo: self.__evUpdatedEventInfo,
				iPlayableService.evStopped: self.__evStopped
			}
		)
		readprio()

	def __evStopped(self):
		self.ecmTimer.stop()

	def __evUpdatedEventInfo(self):
		self.ssid = None
		self.Provider = None
		self.ServiceName = None
		self.caidlist = None
		self.valssid = ""
		self.ecmTimer.stop()
		service = self.session.nav.getCurrentService()
		if service:
			info = service and service.info()
			if info:
				if info.getInfo(iServiceInformation.sIsCrypted):
					ssid = info.getInfo(iServiceInformation.sSID)
					if ssid:
						self.ssid = "%04X" % (ssid)
						self.Provider = info.getInfoString(iServiceInformation.sProvider)
						self.ServiceName = info.getName().replace('\xc2\x86', '').replace('\xc2\x87', '')
						self.caidlist = info.getInfoObject(iServiceInformation.sCAIDs) or None
						if self.caidlist:
							if config.plugins.ccprio.onecaid.value is False and len(self.caidlist) == 1:
								self.ecmTimer.stop()
							else:
								self.parseEcmInfo()
						else:
							self.ecmTimer.stop()

	def parseEcmInfo(self, caidlist=0):
		self.caid = readecminfo()
		if self.caid and len(self.caid) == 2 and len(self.caid[0]) > 0 and len(self.caid[1]) > 0 and self.caid[0] != "0000":
			caid = self.caid[0]
			provid = self.caid[1]
			self.valssid = "%s%s" % (provid, self.ssid)

			if not os_path.exists(PRIOPATH):
				global PRIOLIST_P
				PRIOLIST_P = []

			if self.valssid not in PRIOLIST_P:
				menu = []
				tmplist = []
				providval = "000000"

				for x in self.caidlist:
					m = "%04X" % (x)
					if m == caid:
						providval = provid
					menu.append((_("Caid:") + str(m) + _("\tProvid:") + providval, str(m)))
					tmplist.append(str(m))

				if caid not in tmplist:
					menu.append(("Caid:" + str(caid) + "\tProvid:" + providval, str(caid)))
					tmplist.append(str(caid))

				self.caidlist = tmplist

				if config.plugins.ccprio.askcaid.value is True:
					selection = tmplist.index(str(caid))
					mess = _("Provider") + " :" + self.Provider + "  " + _("Service") + " :" + self.ServiceName

					if config.plugins.ccprio.allcaid.value is False:
						menu = []
						menu.append(("Caid:" + str(caid) + "\tProvid:" + provid, str(caid)))
						selection = 0
						mess += _("\n All Caid:")
						for x in tmplist:
							mess += "%s " % (x)

					self.session.openWithCallback(self.parseEcmInfo_back, ChoiceBox, title=mess, list=menu, selection=selection)
				else:
					self.parseEcmInfo_back((str(caid), str(caid)))
			else:
				self.ecmTimer.stop()
		else:
			self.ecmTimer.start(3000, True)

	def parseEcmInfo_back(self, caidval=0):
		if caidval:
			caid = caidval[1]
			provid = self.caid[1]
			if caid != "" and len(caid) == 4 and caid != "0000" and self.valssid != "":
				val = "P: %s:%s:%s" % (caid, provid, self.ssid)
				self.session.open(MessageBox, _("%s\n\n%s\n%s\n\nPrio entry\n%s") % (_("Add"), _("Provider") + ": " + self.Provider, _("Service") + ": " + self.ServiceName, val), MessageBox.TYPE_INFO, 3)
				PRIOLIST_P.append(self.valssid)
				mode = 'a+' if os_path.exists(PRIOPATH) else 'w'
				with open(PRIOPATH, mode) as file:
					if mode == 'w':
						for p in PRIOLIST_D:
							file.write(p + "\n")
					if config.plugins.ccprio.debug.value is True:
						file.write("# %s  %s Caids:%s\n" % (_("Provider") + ":" + self.Provider, _("Service") + ":" + self.ServiceName, self.caidlist))
					file.write("%s\n" % (val))


class Ccprio_Setup(Screen, ConfigListScreen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.skinName = ["Setup"]
		self.setup_title = _("CCPrioMaker Settings")
		self.onChangedEntry = []
		self["actions"] = ActionMap(
			["SetupActions"],
			{
				"cancel": self.keyCancel,
				"save": self.keySave,
				"ok": self.keySave
			},
			-2
		)
		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("OK"))
		list = []
		list.append(getConfigListEntry(_("CCPrioMaker autostart"), config.plugins.ccprio.autostart))
		list.append(getConfigListEntry(_("Ask for the selection caid"), config.plugins.ccprio.askcaid))
		list.append(getConfigListEntry(_("Ask all caid"), config.plugins.ccprio.allcaid))
		list.append(getConfigListEntry(_("Editing one caid"), config.plugins.ccprio.onecaid))
		list.append(getConfigListEntry(_("Write-Debug"), config.plugins.ccprio.debug))
		ConfigListScreen.__init__(self, list, session=session, on_change=self.changedEntry)
		self.onLayoutFinish.append(self.layoutFinished)

	def layoutFinished(self):
		self.setTitle(self.setup_title)

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)

	def keyRight(self):
		ConfigListScreen.keyRight(self)

	def changedEntry(self):
		for x in self.onChangedEntry:
			x()

	def getCurrentEntry(self):
		return self["config"].getCurrent()[0]

	def getCurrentValue(self):
		return str(self["config"].getCurrent()[1].getText())

	def createSummary(self):
		from Screens.Setup import SetupSummary
		return SetupSummary
