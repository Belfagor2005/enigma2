#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# CCcam Info by AliAbdul
# from Screens.InfoBar import InfoBar
# TOGGLE_SHOW = InfoBar.toggleShow
# modded by lululla 20240314
from __future__ import print_function

from Components.ActionMap import (
	ActionMap,
	NumberActionMap,
	HelpableActionMap,
)
from Components.Console import Console
from Components.Label import Label
from Components.MenuList import MenuList
from Components.MultiContent import (MultiContentEntryText, MultiContentEntryPixmapAlphaBlend)
from Components.ScrollLabel import ScrollLabel
from Components.Sources.StaticText import StaticText
from Components.config import (
	config,
	ConfigSubsection,
	ConfigSelection,
	ConfigText,
	ConfigNumber,
	NoSave,
)
from Screens.HelpMenu import HelpableScreen
from Screens.LocationBox import LocationBox
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Screens.Setup import Setup
from Screens.VirtualKeyBoard import VirtualKeyBoard
from Tools.Directories import (
	fileExists,
	SCOPE_GUISKIN,
	SCOPE_CURRENT_SKIN,
	resolveFilename,
)
from Tools.LoadPixmap import LoadPixmap
from base64 import b64encode
from enigma import (
	eListboxPythonMultiContent,
	gFont,
	loadPNG,
	getDesktop,
	RT_HALIGN_RIGHT,
)
from glob import glob
from os import listdir, remove, rename, system
from os.path import (dirname, exists, isfile)
from skin import getSkinFactor
from urllib.parse import urlparse, urlunparse

# add lululla
from sys import _getframe as getframe
from errno import ENOENT
from enigma import eGetEnigmaDebugLvl
import sys

import requests

from . import CCcamPrioMaker
from . import CCcamOrganizer

import gettext
_ = gettext.gettext


DEFAULT_MODULE_NAME = __name__.split(".")[-1]
forceDebug = eGetEnigmaDebugLvl() > 4
# pathExists = exists


VERSION = "V4"
DATE = "03.06.2025"
CFG = "/etc/CCcam.cfg"
CFG_path = '/etc'
ecmInfoStart = None
global Counter
Counter = 0

AuthHeaders = {
	"User-Agent": "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.113 Safari/537.36",
}

sf = getSkinFactor()


def searchConfig():
	global CFG, CFG_path
	files = glob("/etc/**/CCcam.cfg", recursive=True)
	if files:
		CFG = files[0]
		CFG_path = dirname(CFG)
	print("[CCcamInfo] searchConfig CFG=%s" % CFG)


if sys.version_info >= (2, 7, 9):
	try:
		import ssl
		sslContext = ssl._create_unverified_context()
	except BaseException:
		sslContext = None


def _parse(url):
	url = url.strip()
	print("[CCcamInfo]0 url=%s" % url)
	parsed = urlparse(url)
	scheme = parsed.scheme
	pathz = urlunparse(("", "", parsed.path, parsed.params, parsed.query, parsed.fragment))
	if not pathz:
		pathz = "/"
	host = parsed.hostname
	port = parsed.port or 80
	username = parsed.username or ""
	password = parsed.password or ""

	# Prepare basic auth
	base64string = "%s:%s" % (username, password)
	base64string = b64encode(base64string.encode("utf-8")).decode()
	authHeader = "Basic " + base64string
	AuthHeaders = {"Authorization": authHeader}
	print("[CCcamInfo]1 parsed=%s scheme=%s path=%s host=%s port=%s" % (parsed, scheme, pathz, host, port))

	# Final URL
	url = scheme + "://" + host + ":" + str(port) + pathz
	print("[CCcamInfo]2 url=%s AuthHeaders=%s" % (url, AuthHeaders))
	return url, AuthHeaders


def getPage(url, callback, errback):
	url, auth_headers = _parse(url)
	print("[CCcamInfo] URL requested:", url)

	try:
		response = requests.get(url, headers=auth_headers, timeout=5)
		response.raise_for_status()
		try:
			data = response.content.decode("utf-8")
		except UnicodeDecodeError:
			data = response.content.decode("latin-1")

		callback(data)
	except requests.exceptions.RequestException as error:
		print("[CCcamInfo][getPage] Request error:", error)
		errback(error)
	except Exception as e:
		print("[CCcamInfo][getPage] Unexpected error:", e)
		errback(e)


class HelpableNumberActionMap(NumberActionMap):
	def __init__(self, parent, context, actions, prio):
		alist = []
		adict = {}
		for (action, funchelp) in actions.items():
			alist.append((action, funchelp[1]))
			adict[action] = funchelp[0]
		NumberActionMap.__init__(self, [context], adict, prio)
		parent.helpList.append((self, context, alist))


TranslationHelper = [
	["Current time", _("Current time")],
	["NodeID", _("NodeID")],
	["Uptime", _("Uptime")],
	["Connected clients", _("Connected clients")],
	["Active clients", _("Active clients")],
	["Total handled client ecm's", _("Total handled client ecm's")],
	["Total handled client emm's", _("Total handled client emm's")],
	["Peak load (max queued requests per workerthread)", _("Peak load (max queued requests per workerthread)")],
	["card reader", _("card reader")],
	["no or unknown card inserted", _("no or unknown card inserted")],
	["system:", _("system:")],
	["caid:", _("caid:")],
	["provider:", _("provider:")],
	["provid:", _("provid:")],
	["using:", _("using:")],
	["address:", _("address:")],
	["hops:", _("hops:")],
	["pid:", _("pid:")],
	["share:", _("share:")],
	["handled", _("handled")],
	[" and", _(" and")],
	["card", _("card")],
	["Cardserial", _("Cardserial")],
	["ecm time:", _("ecm time:")]]


def translateBlock(block):
	# Assume TranslationHelper is a list of (key, value) tuples
	for key, value in TranslationHelper:
		if key in block:
			block = block.replace(key, value)
	return block


def getConfigValue(line):
	# Extract the value part after the first ':' (ignoring key)
	value = line.partition(":")[2]
	# Strip leading/trailing whitespace and remove inline comments
	value = value.strip().split("#", 1)[0].strip()
	return value


def notBlackListed(entry):
	try:
		with open(config.cccaminfo.blacklist.value, "r") as f:
			blacklisted_entries = set(line.strip() for line in f)

	except IOError as e:
		print("Error reading blacklist file:", e)
		blacklisted_entries = set()
	return entry not in blacklisted_entries


menu_list = [
	_("CCcam.cfg Basic Line Editor"),
	_("General"),
	_("Clients"),
	_("Active clients"),
	_("Servers"),
	_("Shares"),
	_("Share View"),
	_("Extended Shares"),
	_("Providers"),
	_("Entitlements"),
	_("ecm.info"),
	_("Menu config"),
	_("Local box"),
	_("Remote box"),
	_("CCcam Prio Maker"),
	_("CCcam Organizer"),
	_("Free memory"),
	_("Switch config"),
	_("About")]


if exists(resolveFilename(SCOPE_GUISKIN, "icons/lock_on.png")):
	lock_on = loadPNG(resolveFilename(SCOPE_GUISKIN, "icons/lock_on.png"))
else:
	lock_on = loadPNG("/usr/share/enigma2/skin_default/icons/lock_on.png")

if exists(resolveFilename(SCOPE_GUISKIN, "icons/lock_off.png")):
	lock_off = loadPNG(resolveFilename(SCOPE_GUISKIN, "icons/lock_off.png"))
else:
	lock_off = loadPNG("/usr/share/enigma2/skin_default/icons/lock_off.png")

config.cccamlineedit = ConfigSubsection()
config.cccamlineedit.protocol = NoSave(ConfigSelection(default="C:", choices=[("C:", _("CCcam")), ("N:", _("NewCamd"))]))
config.cccamlineedit.domain = NoSave(ConfigText(fixed_size=False))
config.cccamlineedit.port = NoSave(ConfigNumber())
config.cccamlineedit.username = NoSave(ConfigText(fixed_size=False))
config.cccamlineedit.password = NoSave(ConfigText(fixed_size=False))
config.cccamlineedit.deskey = NoSave(ConfigNumber())
config.cccaminfo = ConfigSubsection()
config.cccaminfo.blacklist = ConfigText(default="/etc/enigma2/CCcamInfo.blacklisted", fixed_size=False)
config.cccaminfo.profiles = ConfigText(default="/etc/enigma2/CCcamInfo.profiles", fixed_size=False)


def getConfigNameAndContent(fileName):
	try:
		with open(fileName, "r") as f:
			content = f.read()
	except IOError:
		return fileName.replace("/etc/", ""), ""

	# Normalize line endings
	content = content.replace("\r", "\n")

	# Extract config name if header is present
	if content.startswith("#CONFIGFILE NAME="):
		name = content[17:]
		idx = name.find("\n")
		if idx != -1:
			name = name[:idx].strip()
		else:
			name = name.strip()
	else:
		name = fileName.replace("/etc/", "")

	return name, content


class CCcamList(MenuList):
	def __init__(self, list):
		MenuList.__init__(self, list, True, eListboxPythonMultiContent)
		self.l.setItemHeight(25)
		self.l.setFont(0, gFont("Regular", 20))
		self.l.setFont(1, gFont("Regular", 32))


class CCcamShareList(MenuList):
	def __init__(self, list):
		MenuList.__init__(self, list, True, eListboxPythonMultiContent)
		self.l.setItemHeight(60)
		self.l.setFont(0, gFont("Regular", 18))
		self.l.setFont(1, gFont("Regular", 32))


class CCcamConfigList(MenuList):
	def __init__(self, list):
		MenuList.__init__(self, list, True, eListboxPythonMultiContent)
		self.l.setItemHeight(30)
		self.l.setFont(0, gFont("Regular", 20))
		self.l.setFont(1, gFont("Regular", 32))


class CCcamShareViewList(MenuList):
	def __init__(self, list):
		MenuList.__init__(self, list, True, eListboxPythonMultiContent)
		self.l.setItemHeight(20)
		self.l.setFont(0, gFont("Regular", 18))
		self.l.setFont(1, gFont("Regular", 32))


class CCcamLineEdit(Setup):
	def __init__(self, session, line):
		self.line = line
		self.extras = []
		self.deskey = "0102030405060708091011121314"
		self.domain = "address.dyndns.org"
		self.username = "username"
		self.password = "password"
		self.port = 12000
		if line == "newC":
			self.protocol = "C:"
		elif line == "newN":
			self.protocol = "N:"
		else:
			mysel = self.line.split()
			self.protocol = mysel[0]
			self.domain = mysel[1]
			self.port = int(mysel[2])
			self.username = mysel[3]
			self.password = mysel[4]
			if mysel[0] == "N:":
				self.deskey = "".join(mysel[5:19])
			self.extras = mysel[19:]

		config.cccamlineedit.protocol.value = self.protocol
		config.cccamlineedit.domain.value = self.domain
		config.cccamlineedit.port.value = self.port
		config.cccamlineedit.username.value = self.username
		config.cccamlineedit.password.value = self.password
		config.cccamlineedit.deskey.value = int(self.deskey)

		Setup.__init__(self, session=session, setup="CCcamLineEdit")
		self.setTitle(_("CCcam Line Editor"))
		if "new" not in self.line:
			self["key_yellow"] = StaticText(_("Remove"))
			self["cccameditactions"] = HelpableActionMap(self, ["ColorActions"], {
				"yellow": (self.keyRemove, _("Remove the Line from CCcam.cfg"))
			}, prio=1, description=_("CCcam Line Edit Actions"))

	def keySave(self):
		# TODO isChanged is always true
		if "new" in self.line or self["config"].isChanged():
			elements = [
				config.cccamlineedit.protocol.value,
				config.cccamlineedit.domain.value,
				str(config.cccamlineedit.port.value),
				config.cccamlineedit.username.value,
				config.cccamlineedit.password.value
			]
			newline = " ".join(elements)
			if config.cccamlineedit.protocol.value == "N:":
				des = "%028d" % config.cccamlineedit.deskey.value
				des = " ".join([des[x:x + 2] for x in range(0, len(des), 2)])
				# N: 127.0.0.1 10000 dummy dummy 01 02 03 04 05 06 07 08 09 10 11 12 13 14
				# des = des[0] + des[1] + " " + des[2] + des[3] + " " + des[4] + des[5] + " " + des[6] + des[7] + " " + des[8] + des[9] + " " + des[10] + des[11] + " " + des[12] + des[13] + " " + des[14] + des[15] + " " + des[16] + des[17] + " " + des[18] + des[19] + " " + des[20] + des[21] + " " + des[22] + des[23] + " " + des[24] + des[25] + " " + des[26] + des[27]
				newline = "%s %s" % (newline, des)
				if self.extras:
					newline = "%s %s" % (newline, " ".join(self.extras))

			lines = fileReadLines(CFG)
			if lines:
				if "new" in self.line:
					lines = [x.strip() for x in lines]
					# add new line at the beginning
					lines.insert(0, newline)
				else:
					destlines = []
					for line in lines:
						if line == self.line:
							destlines.append(newline)
						else:
							destlines.append(line)
					lines = destlines
				fileWriteLines(CFG, lines)
		self.close()

	def keyRemove(self):
		if "new" not in self.line:
			lines = fileReadLines(CFG)
			if lines:
				lines = [line for line in lines if line != self.line]
				fileWriteLines(CFG, lines)
		self.close()


def CCcamListEntry(name, idx):
	screenwidth = getDesktop(0).size().width()
	res = [name]
	if idx == 10:
		idx = "red"
	elif idx == 11:
		idx = "green"
	elif idx == 12:
		idx = "yellow"
	elif idx == 13:
		idx = "blue"
	elif idx == 14:
		idx = "menu"
	elif idx == 15:
		idx = "info"
	if exists(resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % str(idx))):
		png = resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % str(idx))
	else:
		png = "/usr/share/enigma2/skin_default/buttons/key_%s.png" % str(idx)
	if screenwidth and screenwidth == 1920:
		if fileExists(png):
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(10, 7), size=(67, 48), png=LoadPixmap(png)))
		res.append(MultiContentEntryText(pos=(90, 8), size=(900, 40), font=1, text=name))
	else:
		if fileExists(png):
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(35, 25), png=LoadPixmap(png)))
		res.append(MultiContentEntryText(pos=(40, 3), size=(500, 25), font=0, text=name))
	return res


def CCcamServerListEntry(name, color):
	screenwidth = getDesktop(0).size().width()
	res = [name]
	if exists(resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % color)):
		png = resolveFilename(SCOPE_CURRENT_SKIN, "buttons/key_%s.png" % color)
	else:
		png = "/usr/share/enigma2/skin_default/buttons/key_%s.png" % color
	if screenwidth and screenwidth == 1920:
		if fileExists(png):
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(10, 7), size=(67, 48), png=LoadPixmap(png)))
		res.append(MultiContentEntryText(pos=(90, 8), size=(900, 40), font=1, text=name))
	else:
		if fileExists(png):
			res.append(MultiContentEntryPixmapAlphaBlend(pos=(0, 0), size=(35, 25), png=LoadPixmap(png)))
		res.append(MultiContentEntryText(pos=(40, 3), size=(500, 25), font=0, text=name))
	return res


def CCcamShareListEntry(hostname, type, caid, system, uphops, maxdown):
	screenwidth = getDesktop(0).size().width()
	if screenwidth and screenwidth == 1920:
		res = [
			(hostname, type, caid, system, uphops, maxdown),
			MultiContentEntryText(pos=(10, 0), size=(550, 35), font=1, text=hostname),
			MultiContentEntryText(pos=(650, 0), size=(500, 35), font=1, text=_("Type: ") + type, flags=RT_HALIGN_RIGHT),
			MultiContentEntryText(pos=(10, 40), size=(250, 35), font=1, text=_("CaID: ") + caid),
			MultiContentEntryText(pos=(230, 40), size=(250, 35), font=1, text=_("System: ") + system, flags=RT_HALIGN_RIGHT),
			MultiContentEntryText(pos=(520, 40), size=(250, 35), font=1, text=_("Uphops: ") + uphops, flags=RT_HALIGN_RIGHT),
			MultiContentEntryText(pos=(900, 40), size=(250, 35), font=1, text=_("Maxdown: ") + maxdown, flags=RT_HALIGN_RIGHT)
		]
		return res
	else:
		res = [
			(hostname, type, caid, system, uphops, maxdown),
			MultiContentEntryText(pos=(0, 0), size=(250, 20), font=0, text=hostname),
			MultiContentEntryText(pos=(250, 0), size=(250, 20), font=0, text=_("Type: ") + type, flags=RT_HALIGN_RIGHT),
			MultiContentEntryText(pos=(0, 20), size=(250, 20), font=0, text=_("CaID: ") + caid),
			MultiContentEntryText(pos=(250, 20), size=(250, 20), font=0, text=_("System: ") + system, flags=RT_HALIGN_RIGHT),
			MultiContentEntryText(pos=(0, 40), size=(250, 20), font=0, text=_("Uphops: ") + uphops),
			MultiContentEntryText(pos=(250, 40), size=(250, 20), font=0, text=_("Maxdown: ") + maxdown, flags=RT_HALIGN_RIGHT)
		]
		return res


def CCcamShareViewListEntry(caidprovider, providername, numberofcards, numberofreshare):
	screenwidth = getDesktop(0).size().width()
	if screenwidth and screenwidth == 1920:
		res = [(caidprovider, providername, numberofcards),
			   MultiContentEntryText(pos=(10, 5), size=(800, 35), font=1, text=providername),
			   MultiContentEntryText(pos=(1050, 5), size=(50, 35), font=1, text=numberofcards, flags=RT_HALIGN_RIGHT),
			   MultiContentEntryText(pos=(1100, 5), size=(50, 35), font=1, text=numberofreshare, flags=RT_HALIGN_RIGHT)]
		return res
	else:
		res = [(caidprovider, providername, numberofcards),
			   MultiContentEntryText(pos=(0, 0), size=(430, 20), font=0, text=providername),
			   MultiContentEntryText(pos=(430, 0), size=(50, 20), font=0, text=numberofcards, flags=RT_HALIGN_RIGHT),
			   MultiContentEntryText(pos=(480, 0), size=(50, 20), font=0, text=numberofreshare, flags=RT_HALIGN_RIGHT)]
		return res


def CCcamConfigListEntry(file):
	screenwidth = getDesktop(0).size().width()
	res = [(file)]
	try:
		with open(CFG, "r") as f:
			org = f.read()
		if isinstance(org, bytes):
			org = org.decode("utf-8")
	except (IOError, OSError) as e:
		print(str(e))
		org = ""
	(name, content) = getConfigNameAndContent(file)

	if content == org:
		png = lock_on
	else:
		png = lock_off
	if screenwidth and screenwidth == 1920:
		res.append(MultiContentEntryPixmapAlphaBlend(pos=(5, 5), size=(50, 50), png=png))
		res.append(MultiContentEntryText(pos=(85, 0), size=(800, 40), font=1, text=name))
	else:
		res.append(MultiContentEntryPixmapAlphaBlend(pos=(2, 2), size=(25, 25), png=png))
		res.append(MultiContentEntryText(pos=(35, 2), size=(550, 25), font=0, text=name))

	return res


def CCcamMenuConfigListEntry(name, blacklisted):
	screenwidth = getDesktop(0).size().width()
	res = [name]

	if blacklisted:
		png = lock_off
	else:
		png = lock_on
	if screenwidth and screenwidth == 1920:
		res.append(MultiContentEntryPixmapAlphaBlend(pos=(5, 5), size=(50, 50), png=png))
		res.append(MultiContentEntryText(pos=(85, 0), size=(800, 40), font=1, text=name))
	else:
		res.append(MultiContentEntryPixmapAlphaBlend(pos=(2, 2), size=(25, 25), png=png))
		res.append(MultiContentEntryText(pos=(35, 2), size=(550, 25), font=0, text=name))

	return res


class CCcamInfoMain(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Info"))
		self["menu"] = CCcamList([])
		self.working = False
		self.Console = Console()
		if not isfile(CFG):
			print("[CCcamInfo] %s not found" % CFG)
			searchConfig()
		self.url = "http://127.0.0.1:16001"
		self["actions"] = NumberActionMap(["CCcamInfoActions"],
										  {"1": self.keyNumberGlobal,
										   "2": self.keyNumberGlobal,
										   "3": self.keyNumberGlobal,
										   "4": self.keyNumberGlobal,
										   "5": self.keyNumberGlobal,
										   "6": self.keyNumberGlobal,
										   "7": self.keyNumberGlobal,
										   "8": self.keyNumberGlobal,
										   "9": self.keyNumberGlobal,
										   "0": self.keyNumberGlobal,
										   "red": self.red,
										   "green": self.green,
										   "yellow": self.yellow,
										   "blue": self.blue,
										   "menu": self.menu,
										   "info": self.info,
										   "ok": self.okClicked,
										   "cancel": self.close,
										   "up": self.up,
										   "down": self.down,
										   "left": self.left,
										   "right": self.right}, -2)

		self.onLayoutFinish.append(self.updateMenuList)

	def updateMenuList(self):
		self.working = True

		self.menu_list = []
		for x in self.menu_list:
			del self.menu_list[0]

		items = []
		idx = 0
		for x in menu_list:
			if notBlackListed(x):
				items.append(CCcamListEntry(x, idx))
				self.menu_list.append(x)
				idx += 1

		self["menu"].setList(items)
		self.working = False

	def readConfig(self):
		self.url = "http://127.0.0.1:16001"

		username = None
		password = None
		try:
			with open(CFG, 'r') as f:
				for lx in f:
					lx = lx.strip()  # Rimuove eventuali spazi bianchi alla fine delle righe
					if lx.startswith('WEBINFO LISTEN PORT :'):
						port = getConfigValue(lx)
						if port:
							self.url = self.url.replace('16001', port)
					elif lx.startswith('WEBINFO USERNAME :'):
						username = getConfigValue(lx)

					elif lx.startswith('WEBINFO PASSWORD :'):
						password = getConfigValue(lx)
		except IOError as e:
			print("Errore nella lettura del file di configurazione:", e)
			return
		if username and password:
			parsed_url = urlparse(self.url)
			netloc = f"{username}:{password}@{parsed_url.hostname}"
			if parsed_url.port:
				netloc += f":{parsed_url.port}"
			self.url = urlunparse((parsed_url.scheme, netloc, parsed_url.path, '', '', ''))
		config.cccaminfo.profiles.value = ""
		config.cccaminfo.profiles.save()

	def profileSelected(self, url=None):
		if url is not None:
			self.url = url
			config.cccaminfo.profiles.value = self.url
			config.cccaminfo.profiles.save()
			self.showInfo(_("New profile: ") + url, _("Profile"))
		else:
			self.showInfo(_("Using old profile: ") + self.url, _("Profile"))

	def keyNumberGlobal(self, idx):
		if self.working is False and (idx < len(self.menu_list)):
			self.working = True
			sel = self.menu_list[idx]

			if sel == _("General"):
				getPage(self.url, self.showCCcamGeneral, self.getWebpageError)

			elif sel == _("Clients"):
				getPage(self.url + "/clients", self.showCCcamClients, self.getWebpageError)

			elif sel == _("Active clients"):
				getPage(self.url + "/activeclients", self.showCCcamClients, self.getWebpageError)

			elif sel == _("Servers"):
				getPage(self.url + "/servers", self.showCCcamServers, self.getWebpageError)

			elif sel == _("Shares"):
				getPage(self.url + "/shares", self.showCCcamShares, self.getWebpageError)

			elif sel == _("Share View"):
				self.session.openWithCallback(self.workingFinished, CCcamShareViewMenu, self.url)

			elif sel == _("Extended Shares"):
				self.session.openWithCallback(self.workingFinished, CCcamInfoShareInfo, "None", self.url)

			elif sel == _("Providers"):
				getPage(self.url + "/providers", self.showCCcamProviders, self.getWebpageError)

			elif sel == _("Entitlements"):
				getPage(self.url + "/entitlements", self.showCCcamEntitlements, self.getWebpageError)

			elif sel == _("ecm.info"):
				self.session.openWithCallback(self.showEcmInfoFile, CCcamInfoEcmInfoSelection)

			elif sel == _("Menu config"):
				self.session.openWithCallback(self.updateMenuList, CCcamInfoMenuConfig)

			elif sel == _("Local box"):
				self.readConfig()
				self.showInfo(_("Profile: Local box"), _("Local box"))

			elif sel == _("Remote box"):
				self.session.openWithCallback(self.profileSelected, CCcamInfoRemoteBoxMenu)

			elif sel == _("CCcam Prio Maker"):
				self.session.openWithCallback(self.workingFinished, CCcamPrioMaker.Ccprio_Setup)

			elif sel == _("CCcam Organizer"):
				self.session.openWithCallback(self.workingFinished, CCcamOrganizer.OrganizerMenu)

			elif sel == _("Free memory"):
				if not self.Console:
					self.Console = Console()
				self.working = True
				self.Console.ePopen("free", self.showFreeMemory)

			elif sel == _("Switch config"):
				self.session.openWithCallback(self.workingFinished, CCcamInfoConfigSwitcher)

			elif sel == _("CCcam.cfg Basic Line Editor"):
				if isfile(CFG):
					self.showCfgSelection()
				else:
					self.showInfo(_("Could not open the file %s!") % CFG, _("Error"))

			else:
				self.showInfo(_("CCcam Info %s\nby AliAbdul %s\n\nrecoded from Lululla\n\nThis screen shows you the status of CCcam.") % (VERSION, DATE), _("About"))

	def showCfgSelection(self):
		cfgLines = []
		lines = fileReadLines(CFG)
		if lines:
			lines = [x.strip() for x in lines]
			lines = [x for x in lines if x.startswith('C:') or x.startswith('N:')]
			for line in lines:
				lineElements = line.split(" ")
				lineDescription = "%s %s %s" % (lineElements[0], lineElements[1], lineElements[2])
				cfgLines.append((lineDescription, line))
			cfgLines.append((_("Add new CCcam line"), "newC"))
			cfgLines.append((_("Add new NewCamd line"), "newN"))
			self.session.openWithCallback(self.showCfgSelectionCallback, MessageBox, _("Please select a line to edit or select add to create new line."), list=cfgLines)

		else:
			self.workingFinished()

	def showCfgSelectionCallback(self, line):
		if line:
			self.session.openWithCallback(self.workingFinished, CCcamLineEdit, line)
		else:
			self.workingFinished()

	def red(self):
		self.keyNumberGlobal(10)

	def green(self):
		self.keyNumberGlobal(11)

	def yellow(self):
		self.keyNumberGlobal(12)

	def blue(self):
		self.keyNumberGlobal(13)

	def menu(self):
		self.keyNumberGlobal(14)

	def info(self):
		self.keyNumberGlobal(15)

	def okClicked(self):
		self.keyNumberGlobal(self["menu"].getSelectedIndex())

	def up(self):
		if self.working is False:
			self["menu"].up()

	def down(self):
		if self.working is False:
			self["menu"].down()

	def left(self):
		if self.working is False:
			self["menu"].pageUp()

	def right(self):
		if self.working is False:
			self["menu"].pageDown()

	def getWebpageError(self, error):
		print(str(error))
		self.session.openWithCallback(self.workingFinished, MessageBox, _("Error reading webpage!"), MessageBox.TYPE_ERROR)

	def showFile(self, file):
		try:
			with open(file, "r") as f:
				content = f.read()
			if isinstance(content, bytes):
				content = content.decode("utf-8")
		except (IOError, OSError) as e:
			print(str(e))
			content = _("Could not open the file %s!") % file
		self.showInfo(translateBlock(content), "showFile")

	def showEcmInfoFile(self, file=None):
		if file is not None:
			self.showFile("/tmp/" + file)
		self.workingFinished()

	def showCCcamGeneral(self, html):
		start_tag = '<BR><BR>'
		end_tag = '<BR></BODY>'
		html_content = ""
		if not isinstance(html, str):
			self.showInfo(_("Invalid HTML content!"))
			return

		start_idx = html.find(start_tag)
		end_idx = html.find(end_tag)

		if start_idx != -1 and end_idx != -1:
			html_content = html[start_idx + len(start_tag):end_idx]
			html_content = html_content.replace("<BR>", "\n").strip()

		html_content = "\n".join(line for line in html_content.split("\n") if line.strip())

		self.infoToShow = html_content

		if not isinstance(self.url, str):
			self.showInfo(_("Invalid URL!"))
			return

		try:
			# getPage(self.url + "/shares").addCallback(self.showCCcamGeneral2).addErrback(self.getWebpageError)
			getPage(self.url + "/shares", self.showCCcamGeneral2, self.getWebpageError)
		except Exception as e:
			print(str(e))
			self.showInfo(_("Error reading webpage!"), _("Error"))

	def showCCcamGeneral2(self, html):
		version_start = "Welcome to CCcam"
		version_start_idx = html.find(version_start)
		if version_start_idx != -1:
			version_start_idx += len(version_start)
			version_end_idx = html.find(" ", version_start_idx)
			if version_end_idx != -1:
				version = html[version_start_idx:version_end_idx].strip()
				self.infoToShow = "%s%s\n%s" % (_("Version: "), version, self.infoToShow)

		shares_start = "Available shares:"
		shares_start_idx = html.find(shares_start)

		if shares_start_idx != -1:
			shares_start_idx += len(shares_start)
			shares_end_idx = html.find("\n", shares_start_idx)
			if shares_end_idx != -1:
				shares_info = html[shares_start_idx:shares_end_idx].strip()
				self.showInfo(translateBlock("%s %s\n%s" % (_("Available shares:"), shares_info, self.infoToShow)), _("General"))
			else:
				shares_info = html[shares_start_idx:].strip()
				self.showInfo(translateBlock("%s %s\n%s" % (_("Available shares:"), shares_info, self.infoToShow)), _("General"))
		else:
			self.showInfo(translateBlock(self.infoToShow), _("General"))

	def showCCcamClients(self, html):
		first_line = True
		client_list = []
		info_list = []
		lines = html.split("\n")

		for line in lines:
			if '|' in line:
				if first_line:
					first_line = False
				else:
					fields = line.split('|')
					if len(fields) > 8:
						username = fields[1].strip()
						if username:
							hostname = fields[2].strip()
							connected = fields[3].strip()
							idle_time = fields[4].strip()
							ecm = fields[5].strip()
							emm = fields[6].strip()
							version = fields[7].strip() or "N/A"
							share = fields[8].strip()
							ecm_emm = f"ECM: {ecm} - EMM: {emm}"
							info_list.append([
								username,
								_("Hostname: ") + hostname,
								_("Connected: ") + connected,
								_("Idle Time: ") + idle_time,
								_("Version: ") + version,
								_("Last used share: ") + share,
								ecm_emm
							])
							client_list.append(username)
		self.set_title = _("CCcam Clients Info")
		self.openSubMenu(client_list, info_list, self.set_title)

	def showCCcamServers(self, html):
		first_line = True
		info_list = []
		lines = html.split("\n")

		for line in lines:
			if '|' in line:
				if first_line:
					first_line = False
				else:
					fields = line.split('|')
					if len(fields) > 7:
						hostname = fields[1].strip()
						if hostname:
							connected = fields[2].strip()
							server_type = fields[3].strip()
							version = fields[4].strip() or "N/A"
							nodeid = fields[5].strip() or "N/A"
							cards = fields[6].strip()
							info_list.append([
								hostname,
								_("Cards: ") + cards,
								_("Type: ") + server_type,
								_("Version: ") + version,
								_("NodeID: ") + nodeid,
								_("Connected: ") + connected
							])
		self.session.openWithCallback(self.workingFinished, CCcamInfoServerMenu, info_list, self.url)

	def showCCcamShares(self, html):
		first_line = True
		shares_list = []
		info_list = []
		lines = html.split("\n")
		for line in lines:
			if '|' in line:
				if first_line:
					first_line = False
				else:
					fields = line.split('|')
					if len(fields) > 7:
						hostname = fields[1].strip()
						if hostname:
							share_type = fields[2].strip()
							caid = fields[3].strip()
							system = fields[4].strip()
							share_info = fields[6].strip()
							parts = share_info.split()
							if len(parts) >= 2:
								uphops = parts[0]
								maxdown = parts[1]
							else:
								uphops = ""
								maxdown = ""
							if len(caid) == 3:
								caid = "0" + caid
							info_list.append([
								hostname,
								_("Type: ") + share_type,
								_("CaID: ") + caid,
								_("System: ") + system,
								_("Uphops: ") + uphops,
								_("Maxdown: ") + maxdown
							])
							shares_list.append(hostname + " - " + _("CaID: ") + caid)

		self.set_title = _("CCcam Shares Info")
		self.openSubMenu(shares_list, info_list, self.set_title)

	def showCCcamProviders(self, html):
		first_line = True
		providers_list = []
		info_list = []
		lines = html.split("\n")
		for line in lines:
			if '|' in line:
				if first_line:
					first_line = False
				else:
					fields = line.split('|')
					if len(fields) > 5:
						caid = fields[1].strip()
						if caid:
							provider = fields[2].strip()
							provider_name = fields[3].strip()
							system = fields[4].strip()
							info_list.append([
								_("CaID: ") + caid,
								_("Provider: ") + provider,
								_("Provider Name: ") + provider_name,
								_("System: ") + system
							])
							providers_list.append(_("CaID: ") + caid + " - " + _("Provider: ") + provider)

		self.set_title = _("CCcam Provider Info")
		self.openSubMenu(providers_list, info_list, self.set_title)

	def showCCcamEntitlements(self, html):
		if '<PRE>' in html:
			start_idx = html.find('<PRE>') + len('<PRE>')
			end_idx = html.find('</PRE>')
			if start_idx != -1 and end_idx != -1:
				extracted_html = html[start_idx:end_idx].replace("\n\n", "\n").strip()

				if not extracted_html:
					extracted_html = _("No card inserted!")
				self.showInfo(translateBlock(extracted_html), _("Entitlements"))
			else:
				self.showInfo(_("Error processing HTML!"), _("Entitlements"))
		else:
			self.showInfo(_("Error reading webpage!"), _("Entitlements"))

	def showInfo(self, info, set_title):
		self.session.openWithCallback(self.workingFinished, CCcamInfoInfoScreen, info, set_title)

	def openSubMenu(self, list, infoList, set_title):
		self.session.openWithCallback(self.workingFinished, CCcamInfoSubMenu, list, infoList, set_title)

	def workingFinished(self, callback=None):
		self.working = False

	def showFreeMemory(self, result, retval, extra_args):
		if retval == 0:
			if result.__contains__("Total:"):
				idx = result.index("Total:")
				result = result[idx + 6:]
				tmpList = result.split(" ")
				items = []
				for x in tmpList:
					if x != "":
						items.append(x)
				self.showInfo("%s\n\n  %s %s\n  %s %s\n  %s %s" % (_("Free memory:"), _("Total:"), items[0], _("Used:"), items[1], _("Free:"), items[2]), _("Free memory"))
			else:
				self.showInfo(result, _("Free memory"))
		else:
			self.showInfo(str(result), _("Free memory"))


class CCcamInfoEcmInfoSelection(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.setTitle(_("CCcam ECM Info"))
		items = []
		tmp = listdir("/tmp/")
		for x in tmp:
			if x.endswith('.info') and x.startswith('ecm'):
				items.append(x)
		self["list"] = MenuList(items)

		self["actions"] = ActionMap(["CCcamInfoActions"], {"ok": self.ok, "cancel": self.close}, -1)

	def ok(self):
		self.close(self["list"].getCurrent())


class CCcamInfoInfoScreen(Screen):
	def __init__(self, session, info, set_title):
		Screen.__init__(self, session)
		self.setTitle(set_title)
		self["text"] = ScrollLabel(info)
		self["actions"] = ActionMap(
			["CCcamInfoActions"],
			{
				"ok": self.close,
				"cancel": self.close,
				"up": self["text"].pageUp,
				"down": self["text"].pageDown,
				"left": self["text"].pageUp,
				"right": self["text"].pageDown
			},
			-1
		)
		self["key_red"] = Label(_("Cancel"))
		self["shortcuts"] = ActionMap(
			["ShortcutActions"],
			{
				"red": self.close
			}
		)


class CCcamShareViewMenu(Screen, HelpableScreen):
	def __init__(self, session, url):
		Screen.__init__(self, session)
		HelpableScreen.__init__(self)
		self.session = session
		self.setTitle(_("CCcam Share Info"))
		self.url = url
		self.list = []
		self.providers = {}
		self.uphop = -1
		self.working = True
		self["list"] = CCcamShareViewList([])
		self["uphops"] = Label()
		self["cards"] = Label()
		self["providers"] = Label()
		self["reshare"] = Label()
		self["title"] = Label()
		self["actions"] = HelpableNumberActionMap(
			self,
			"CCcamInfoActions",
			{
				"cancel": (self.exit, _("close share view")),
				"0": (self.getUphop, _("show cards with uphop 0")),
				"1": (self.getUphop, _("show cards with uphop 1")),
				"2": (self.getUphop, _("show cards with uphop 2")),
				"3": (self.getUphop, _("show cards with uphop 3")),
				"4": (self.getUphop, _("show cards with uphop 4")),
				"5": (self.getUphop, _("show cards with uphop 5")),
				"6": (self.getUphop, _("show cards with uphop 6")),
				"7": (self.getUphop, _("show cards with uphop 7")),
				"8": (self.getUphop, _("show cards with uphop 8")),
				"9": (self.getUphop, _("show cards with uphop 9")),
				"green": (self.showAll, _("show all cards")),
				"incUphop": (self.incUphop, _("increase uphop by 1")),
				"decUphop": (self.decUphop, _("decrease uphop by 1")),
				"ok": (self.getServer, _("get the cards' server"))
			},
			-1
		)

		self.onLayoutFinish.append(self.getProviders)
		self["key_red"] = Label(_("Cancel"))
		self["actions"] = ActionMap(["CCcamInfoActions"], {"cancel": self.close, "red": self.close}, -1)

	def exit(self):
		if self.working is False:
			self.close()

	def getProviders(self):
		getPage(self.url + "/providers", self.readProvidersCallback, self.readError)

	def readError(self, error=None):
		self.session.open(MessageBox, _("Error reading webpage!"), MessageBox.TYPE_ERROR)
		self.working = False

	def readSharesCallback(self, html):
		firstLine = True
		providerList = []
		countList = []
		shareList = []
		reshareList = []
		self.hostList = []
		self.caidList = []
		count = 0
		totalcards = 0
		totalproviders = 0
		resharecards = 0
		numberofreshare = 0
		ulevel = 0
		lines = html.split("\n")
		for line in lines:
			if '|' in line:
				if firstLine:
					firstLine = False
					continue
				parts = line.split('|')
				if len(parts) > 7:
					hostname = parts[1].strip()
					if hostname:
						caid = parts[3].strip()
						provider = parts[5].strip()
						caidprovider = self.formatCaidProvider(caid, provider)
						down = parts[6].strip()
						if ' ' in down:
							up, down = down.split(' ', 1)
						else:
							up = down
							down = ""
						if self.uphop == -1:
							maxdown = down.strip()
							numberofcards = 1
							providername = self.providers.get(caidprovider, 'Multiple Providers given')
							numberofreshare = 1 if int(maxdown) > 0 else 0
							resharecards += numberofreshare
							if caidprovider not in providerList:
								providerList.append(caidprovider)
								countList.append(numberofcards)
								reshareList.append(numberofreshare)
								shareList.append(CCcamShareViewListEntry(caidprovider, providername, str(numberofcards), str(numberofreshare)))
								self.list.append([caidprovider, providername, numberofcards, numberofreshare])
								totalproviders += 1
							else:
								index = providerList.index(caidprovider)
								count = countList[index] + 1
								countList[index] = count
								numberofcards = count

								if int(maxdown) > 0:
									reshareList[index] += 1
									numberofreshare = reshareList[index]
									resharecards += 1
								else:
									numberofreshare = reshareList[index]
								providername = self.providers.get(caidprovider, 'Multiple Providers given')
								shareList[index] = CCcamShareViewListEntry(caidprovider, providername, str(numberofcards), str(numberofreshare))
							self.hostList.append(hostname)
							self.caidList.append(caidprovider)
							totalcards += 1
							ulevel = _("All")
						else:
							if int(up.strip()) == self.uphop:
								providername = self.providers.get(caidprovider, 'Multiple Providers given')
								if caidprovider not in providerList:
									providerList.append(caidprovider)
									countList.append(1)
									reshareList.append(1 if int(down) > 0 else 0)
									shareList.append(CCcamShareViewListEntry(caidprovider, providername, '1', str(reshareList[-1])))
									self.list.append([caidprovider, providername, '1', str(reshareList[-1])])
									totalproviders += 1
								else:
									index = providerList.index(caidprovider)
									count = countList[index] + 1
									countList[index] = count
									numberofcards = count
									if int(down) > 0:
										reshareList[index] += 1
										numberofreshare = reshareList[index]
										resharecards += 1
									else:
										numberofreshare = reshareList[index]
									shareList[index] = CCcamShareViewListEntry(caidprovider, providername, str(numberofcards), str(numberofreshare))
								self.hostList.append(hostname)
								self.caidList.append(caidprovider)
								totalcards += 1
								ulevel = str(self.uphop)
		self.instance.setTitle("%s (%s %d) %s %s" % (_("Share View"), _("Total cards:"), totalcards, _("Hops:"), ulevel))
		self["title"].setText("%s (%s %d) %s %s" % (_("Share View"), _("Total cards:"), totalcards, _("Hops:"), ulevel))
		self["list"].setList(shareList)
		self["uphops"].setText("%s %s" % (_("Hops:"), ulevel))
		self["cards"].setText("%s %s" % (_("Total cards:"), totalcards))
		self["providers"].setText("%s %s" % (_("Providers:"), totalproviders))
		self["reshare"].setText("%s %d" % (_("Reshare:"), resharecards))
		self.working = False

	def readProvidersCallback(self, html):
		firstLine = True
		lines = html.split("\n")
		for line in lines:
			if '|' in line:
				if firstLine:
					firstLine = False
					continue
				parts = line.split('|')
				if len(parts) > 5:
					caid = parts[1].strip()
					if caid:
						provider = parts[2].strip()
						providername = parts[3].strip()
						caidprovider = self.formatCaidProvider(caid, provider)
						self.providers.setdefault(caidprovider, providername)
		getPage(self.url + "/shares", self.readSharesCallback, self.readError)

	def formatCaidProvider(self, caid, provider):
		pos = provider.find(",")
		if pos != -1:
			provider = provider[pos + 1:]
			pos = provider.find(",")
			if pos != -1:
				provider = provider[0:pos]

		if len(provider) == 0:
			provider = "0000"
		elif len(provider) == 1:
			provider = "000" + provider
		elif len(provider) == 2:
			provider = "00" + provider
		elif len(provider) == 3:
			provider = "0" + provider

		if len(caid) == 3:
			caid = "0" + caid

		if caid.startswith("0500") and len(provider) == 5:
			caid = "050"
		elif caid.startswith("0500") and len(provider) == 6:
			caid = "05"

		if caid.startswith("06"):
			caidprovider = caid
		elif caid.startswith("0d22"):
			caidprovider = caid
		elif caid.startswith("0d05"):
			caidprovider = caid
		elif caid.startswith("09"):
			caidprovider = caid
		elif caid.startswith("17"):
			caidprovider = caid
		elif caid.startswith("18"):
			caidprovider = caid
		elif caid.startswith("4a"):
			caidprovider = caid
		else:
			caidprovider = caid + provider
		return caidprovider

	def getUphop(self, uphop):
		self.uphop = uphop
		self.getProviders()

	def showAll(self):
		self.uphop = -1
		self.getProviders()

	def incUphop(self):
		if self.uphop < 9:
			self.uphop += 1
			self.getProviders()

	def decUphop(self):
		if self.uphop > -1:
			self.uphop -= 1
			self.getProviders()

	def getServer(self):
		server = _("Servers:") + " \n"
		sel = self["list"].getCurrent()
		if sel is not None:
			e = 0
			while e < len(self.caidList):
				if sel[0][0] == self.caidList[e]:
					pos = self.hostList[e].find(":")
					if pos != -1:
						server += self.hostList[e][0:pos] + "\n"
					else:
						server += self.hostList[e] + "\n"
				e += 1
			self.session.open(CCcamInfoInfoScreen, server, _("Servers"))


class CCcamInfoSubMenu(Screen):
	def __init__(self, session, list, infoList, set_title):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_(set_title))
		self.infoList = infoList
		self["list"] = MenuList(list)
		self["info"] = Label()
		self["key_green"] = Label(_("info"))
		self["key_red"] = Label(_("Cancel"))
		self["actions"] = ActionMap(["CCcamInfoActions"], {"ok": self.okClicked, "cancel": self.close, "red": self.close, "green": self.okClicked}, -1)

		self["list"].onSelectionChanged.append(self.showInfo)
		self.onLayoutFinish.append(self.showInfo)

	def okClicked(self):
		info = self.getInfo()
		if info != "":
			self.session.open(MessageBox, info, MessageBox.TYPE_INFO)

	def showInfo(self):
		info = self.getInfo()
		self["info"].setText(info)

	def getInfo(self):
		try:
			idx = self["list"].getSelectedIndex()

			info = ""
			infoList = self.infoList[idx]
			for x in infoList:
				info += x + "\n"

			return info
		except BaseException:
			return ""


class CCcamInfoServerMenu(Screen):
	def __init__(self, session, infoList, url):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Server Info"))
		self.infoList = infoList
		self.url = url

		items = []
		for x in self.infoList:
			if x[5].replace(_("Connected: "), "") == "":  # offline - red
				items.append(CCcamServerListEntry(x[0], "red"))
			elif x[1] == _("Cards: 0"):  # online with no card - blue
				items.append(CCcamServerListEntry(x[0], "blue"))
			else:  # online with cards - green
				items.append(CCcamServerListEntry(x[0], "green"))
		self["list"] = CCcamList(items)
		self["info"] = Label()
		self["key_red"] = Label(_("Cancel"))
		self["actions"] = ActionMap(["CCcamInfoActions"], {"ok": self.okClicked, "cancel": self.close, "red": self.close, "green": self.okClicked}, -1)
		self["list"].onSelectionChanged.append(self.showInfo)
		self.onLayoutFinish.append(self.showInfo)

	def showInfo(self):
		info = self.getInfo()
		self["info"].setText(info)

	def getInfo(self):
		try:
			idx = self["list"].getSelectedIndex()

			info = ""
			infoList = self.infoList[idx]
			for x in infoList:
				info += x + "\n"

			return info
		except BaseException:
			return ""

	def okClicked(self):
		sel = self["list"].getCurrent()
		if sel is not None:
			self.session.open(CCcamInfoShareInfo, sel[0], self.url)


class CCcamInfoRemoteBox:
	def __init__(self, name, ip, username, password, port):
		self.name = name
		self.ip = ip
		self.username = username
		self.password = password
		self.port = port


class CCcamInfoProfileSetup(Setup):
	def __init__(self, session, profile):
		Setup.__init__(self, session=session, setup="CCcamProfile")
		self.setTitle(_("CCcam Info Config Menu"))
		config.cccaminfo.name.value = profile.name
		config.cccaminfo.ip.value = profile.ip
		config.cccaminfo.username.value = profile.username
		config.cccaminfo.password.value = profile.password
		config.cccaminfo.port.value = profile.port

		self["actions"] = ActionMap(["CCcamInfoActions"], {"ok": self.okClicked, "cancel": self.close}, -2)

	def okClicked(self):
		self.close(CCcamInfoRemoteBox(config.cccaminfo.name.value, config.cccaminfo.ip.value, config.cccaminfo.username.value, config.cccaminfo.password.value, config.cccaminfo.port.value))

	def keySave(self):
		self.close(CCcamInfoRemoteBox(config.cccaminfo.name.value, config.cccaminfo.ip.value, config.cccaminfo.username.value, config.cccaminfo.password.value, config.cccaminfo.port.value))

	def keyCancel(self):
		self.close(None)


class CCcamInfoRemoteBoxMenu(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Remote Info"))
		self.list = []
		self.profiles = []
		self["key_red"] = Label(_("Delete"))
		self["key_green"] = Label(_("New"))
		self["key_yellow"] = Label(_("Location"))
		self["key_blue"] = Label(_("Edit"))
		self["list"] = MenuList([])
		self["actions"] = ActionMap(
			["CCcamInfoActions"],
			{
				"cancel": self.exit,
				"ok": self.profileSelected,
				"red": self.delete,
				"green": self.new,
				"yellow": self.location,
				"blue": self.edit
			},
			-1
		)
		self.onLayoutFinish.append(self.readProfiles)

	def readProfiles(self):
		self.list = []  # Ensure the list is initialized
		self.profiles = []  # Ensure the profiles list is initialized
		try:
			with open(config.plugins.cccaminfo.profiles.value, "r") as f:
				content = f.read()

		except IOError as e:
			# Log the error or handle it appropriately
			print("Error reading profiles file:", e)
			content = ""
		profiles = content.split("\n")
		for profile in profiles:
			if "|" in profile:
				tmp = profile.split("|")
				if len(tmp) == 5:
					name = tmp[0].strip()
					ip = tmp[1].strip()
					username = tmp[2].strip()
					password = tmp[3].strip()
					try:
						port = int(tmp[4].strip())
						if 1 <= port <= 65535:  # Ensure port is in a valid range
							self.list.append(name)
							self.profiles.append(CCcamInfoRemoteBox(name, ip, username, password, port))
						else:
							print("Invalid port number {port} in profile:", name)
					except ValueError:
						print("Invalid port number format in profile:", name)
		self["list"].setList(self.list)

	def saveConfigs(self):
		content = ""
		for x in self.profiles:
			content += f"{x.name}|{x.ip}|{x.username}|{x.password}|{x.port}\n"
		try:
			with open(config.cccaminfo.profiles.value, "w") as f:
				f.write(content.strip())  # Strip to remove any leading/trailing newlines

		except IOError as e:
			self.session.open(MessageBox, _("Could not save the config file! Error: %s") % str(e), MessageBox.TYPE_ERROR)

	def exit(self):
		self.saveConfigs()
		self.close(None)

	def profileSelected(self):
		self.saveConfigs()
		if len(self.list) > 0:
			idx = self["list"].getSelectionIndex()
			cur = self.profiles[idx]
			if cur.ip == "":
				url = None
			else:
				if cur.username != "" and cur.password != "":
					url = "http://%s:%s@%s:%d" % (cur.username, cur.password, cur.ip, cur.port)
				else:
					url = "http://%s:%d" % (cur.ip, cur.port)
			self.close(url)

	def delete(self):
		if len(self.list) > 0:
			idx = self["list"].getSelectionIndex()
			del self.list[idx]
			del self.profiles[idx]
			self["list"].setList(self.list)

	def new(self):
		self.session.openWithCallback(self.newCallback, CCcamInfoProfileSetup, CCcamInfoRemoteBox("Profile", "192.168.2.12", "", "", 16001))  # NOSONAR

	def newCallback(self, callback):
		if callback:
			self.list.append(callback.name)
			self.profiles.append(callback)
			self["list"].setList(self.list)

	def location(self):
		self.session.openWithCallback(self.locationCallback, LocationBox)

	def locationCallback(self, callback):
		if callback:
			config.cccaminfo.profiles.value = ("%s/CCcamInfo.profiles" % callback).replace("//", "/")
			config.cccaminfo.profiles.save()
		del self.list
		self.list = []
		del self.profiles
		self.profiles = []
		self.readProfiles()

	def edit(self):
		if len(self.list) > 0:
			idx = self["list"].getSelectionIndex()
			self.session.openWithCallback(self.editCallback, CCcamInfoProfileSetup, self.profiles[idx])

	def editCallback(self, callback):
		if callback:
			idx = self["list"].getSelectionIndex()
			del self.list[idx]
			del self.profiles[idx]
			self.list.append(callback.name)
			self.profiles.append(callback)
			self["list"].setList(self.list)


class CCcamInfoShareInfo(Screen):
	def __init__(self, session, hostname, url):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Share Info"))
		self.hostname = hostname
		self.url = url
		self.list = []
		self.uphops = -1
		self.maxdown = -1
		self.working = True

		self["key_red"] = Label(_("Uphops +"))
		self["key_green"] = Label(_("Uphops -"))
		self["key_yellow"] = Label(_("Maxdown +"))
		self["key_blue"] = Label(_("Maxdown -"))
		self["list"] = CCcamShareList([])
		self["actions"] = ActionMap(
			["CCcamInfoActions"],
			{
				"cancel": self.exit,
				"red": self.uhopsPlus,
				"green": self.uhopsMinus,
				"yellow": self.maxdownPlus,
				"blue": self.maxdownMinus
			},
			-1
		)
		self.onLayoutFinish.append(self.readShares)

	def exit(self):
		if self.working is False:
			self.close()

	def readShares(self):
		getPage(self.url + "/shares", self.readSharesCallback, self.readSharesError)

	def readSharesError(self, error=None):
		self.session.open(MessageBox, _("Error reading webpage!"), MessageBox.TYPE_ERROR)
		self.working = False

	def readSharesCallback(self, html):
		firstLine = True
		shareList = []
		count = 0
		lines = html.split("\n")
		for line in lines:
			if '|' in line:
				if firstLine:
					firstLine = False
					continue
				parts = line.split("|")
				if len(parts) > 7:
					hostname = parts[1].strip()
					if (self.hostname == "None" or self.hostname == hostname) and hostname:
						type = parts[2].strip()
						caid = parts[3].strip()
						system = parts[4].strip()
						# Clean up and parse the uphops and maxdown values
						string = parts[6].strip()
						idx = string.find(" ")
						uphops = string[:idx].strip()
						maxdown = string[idx + 1:].strip()
						# Format CAID if necessary
						if len(caid) == 3:
							caid = "0" + caid
						# Append data to the lists
						shareList.append(CCcamShareListEntry(hostname, type, caid, system, uphops, maxdown))
						self.list.append([hostname, type, caid, system, uphops, maxdown])
						count += 1
		# Format uplinks and maxdown values for display
		textUhops = _("All") if self.uphops < 0 else str(self.uphops)
		textMaxdown = _("All") if self.maxdown < 0 else str(self.maxdown)
		# Update the instance title and list
		self.instance.setTitle(
			"%s %d (%s%s / %s%s)" % (
				_("Available shares:"), count,
				_("Uphops: "), textUhops,
				_("Maxdown: "), textMaxdown
			)
		)
		self["list"].setList(shareList)
		self.working = False

	def uhopsPlus(self):
		if self.working is False:
			self.uphops += 1
			if self.uphops > 9:
				self.uphops = -1
			self.refreshList()

	def uhopsMinus(self):
		if self.working is False:
			self.uphops -= 1
			if self.uphops < -1:
				self.uphops = 9
			self.refreshList()

	def maxdownPlus(self):
		if self.working is False:
			self.maxdown += 1
			if self.maxdown > 9:
				self.maxdown = -1
			self.refreshList()

	def maxdownMinus(self):
		if self.working is False:
			self.maxdown -= 1
			if self.maxdown < -1:
				self.maxdown = 9
			self.refreshList()

	def refreshList(self):
		shareList = []
		count = 0
		self.working = True

		for x in self.list:
			(hostname, type, caid, system, uphops, maxdown) = x
			if (uphops == str(self.uphops) or self.uphops == -1) and (maxdown == str(self.maxdown) or self.maxdown == -1):
				shareList.append(CCcamShareListEntry(hostname, type, caid, system, uphops, maxdown))
				count += 1

		if self.uphops < 0:
			textUhops = _("All")
		else:
			textUhops = str(self.uphops)

		if self.maxdown < 0:
			textMaxdown = _("All")
		else:
			textMaxdown = str(self.maxdown)

		self.instance.setTitle("%s %d (%s%s / %s%s)" % (_("Available shares:"), count, _("Uphops: "), textUhops, _("Maxdown: "), textMaxdown))
		self["list"].setList(shareList)
		self.working = False


class CCcamInfoConfigSwitcher(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Config Switcher"))
		self["key_red"] = Label(_("Delete"))
		self["key_green"] = Label(_("Activate"))
		self["key_yellow"] = Label(_("Rename"))
		self["key_blue"] = Label(_("Content"))
		self["list"] = CCcamConfigList([])
		self["actions"] = ActionMap(
			["CCcamInfoActions"],
			{
				"ok": self.activate,
				"cancel": self.close,
				"red": self.delete,
				"green": self.activate,
				"yellow": self.rename,
				"blue": self.showContent
			},
			-1
		)
		self.onLayoutFinish.append(self.showConfigs)

	def showConfigs(self):
		items = []

		try:
			files = listdir(CFG_path)
		except OSError:
			files = []

		for file in files:
			if file.startswith("CCcam_") and file.endswith(".cfg"):
				items.append(CCcamConfigListEntry(CFG_path + "/" + file))

		self["list"].setList(items)

	def delete(self):
		fileName = self["list"].getCurrent()
		if fileName is not None:
			self.fileToDelete = fileName[0]
			self.session.openWithCallback(self.deleteConfirmed, MessageBox, (_("Delete %s?") % self.fileToDelete))

	def deleteConfirmed(self, yesno):
		if yesno:
			remove(self.fileToDelete)
			if fileExists(self.fileToDelete):
				self.session.open(MessageBox, _("Delete failed!"), MessageBox.TYPE_ERROR)
			else:
				self.session.open(MessageBox, _("Deleted %s!") % self.fileToDelete, MessageBox.TYPE_INFO)
				self.showConfigs()

	def activate(self):
		fileName = self["list"].getCurrent()
		if fileName is not None:
			fileName = fileName[0]
			# Delete old backup
			backupFile = "%s.backup" % CFG
			if fileExists(backupFile):
				remove(backupFile)
			# Create a backup of the original /var/etc/CCcam.cfg file
			rename(CFG, backupFile)
			# Now copy the selected cfg file
			system("cp -f %s %s" % (fileName, CFG))
			self.showConfigs()

	def rename(self):
		fileName = self["list"].getCurrent()
		if fileName is not None:
			self.fileToRename = fileName[0]
			(name, sel) = getConfigNameAndContent(self.fileToRename)
			self.session.openWithCallback(self.renameCallback, VirtualKeyBoard, title=_("Rename to:"), text=name)

	def renameCallback(self, callback):
		if callback:
			try:
				# Leggi il contenuto del file
				with open(self.fileToRename, "r") as file:
					content = file.read()

			except IOError:
				self.session.open(MessageBox, _("Rename failed!"), MessageBox.TYPE_ERROR)
				return

			content = content.replace("\r", "\n")
			if content.startswith("#CONFIGFILE NAME=") and "\n" in content:
				idx = content.index("\n") + 1
				content = content[idx:]

			content = "#CONFIGFILE NAME=%s\n%s" % (callback, content)
			try:
				with open(self.fileToRename, "w") as file:
					file.write(content)
				self.session.open(MessageBox, _("Renamed %s!") % self.fileToRename, MessageBox.TYPE_INFO)
				self.showConfigs()
			except IOError:
				self.session.open(MessageBox, _("Rename failed!"), MessageBox.TYPE_ERROR)

	def showContent(self):
		fileName = self["list"].getCurrent()
		if fileName is not None and len(fileName) > 0:
			try:
				with open(fileName[0], "r") as f:
					content = f.read()

			except IOError as e:
				# Handle file opening errors specifically
				content = _("Could not open the file %s! Error: %s") % (fileName[0], str(e))
			except Exception as e:
				# Handle other unexpected errors
				content = _("An unexpected error occurred: %s") % str(e)
			self.session.open(CCcamInfoInfoScreen, content, _("CCcam Config Switcher"))


class CCcamInfoMenuConfig(Screen):
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.setTitle(_("CCcam Info Config"))
		self["key_red"] = Label(_("Cancel"))
		self["key_green"] = Label(_("Save"))
		self["key_yellow"] = Label(_("Location"))
		self["list"] = CCcamConfigList([])
		self.getBlacklistedMenuEntries()
		self["actions"] = ActionMap(
			["CCcamInfoActions"],
			{
				"ok": self.changeState,
				"cancel": self.close,
				"red": self.close,
				"green": self.save,
				"yellow": self.location
			},
			-1
		)
		self.onLayoutFinish.append(self.showConfigs)

	def getBlacklistedMenuEntries(self):
		try:
			with open(config.cccaminfo.blacklist.value, "r") as f:
				content = f.read()
			if isinstance(content, bytes):
				content = content.decode("utf-8")  # Decodifica per Python 2 se necessario
			self.blacklisted = content.split("\n")
		except (IOError, OSError) as e:  # Cattura errori legati ai file
			self.blacklisted = []
			print(str(e))

	def changeState(self):
		cur = self["list"].getCurrent()
		if cur is not None:
			cur = cur[0]
			if cur in self.blacklisted:
				idx = 0
				for x in self.blacklisted:
					if x == cur:
						del self.blacklisted[idx]
						break
					idx += 1
			else:
				self.blacklisted.append(cur)
		self.showConfigs()

	def showConfigs(self):
		items = []
		for x in menu_list:
			if x != _("Menu config"):
				if x in self.blacklisted:
					items.append(CCcamMenuConfigListEntry(x, True))
				else:
					items.append(CCcamMenuConfigListEntry(x, False))
		self["list"].setList(items)

	def save(self):
		# Join blacklisted entries with newline and ensure no double newlines
		content = "\n".join(self.blacklisted).strip() + "\n"
		try:
			with open(config.cccaminfo.blacklist.value, "w") as f:
				f.write(content)

			self.session.open(MessageBox, _("Configfile %s saved.") % config.cccaminfo.blacklist.value, MessageBox.TYPE_INFO)
		except IOError as e:
			# Log the error or handle it appropriately
			self.session.open(MessageBox, _("Could not save configfile %s! Error: %s") % (config.cccaminfo.blacklist.value, str(e)), MessageBox.TYPE_ERROR)

	def location(self):
		self.session.openWithCallback(self.locationCallback, LocationBox)

	def locationCallback(self, callback):
		if callback:
			config.cccaminfo.blacklist.value = ("%s/CCcamInfo.blacklisted" % callback).replace("//", "/")
			config.cccaminfo.blacklist.save()


def fileReadLines(filename, default=None, source=DEFAULT_MODULE_NAME, debug=False):
	lines = None
	try:
		with open(filename) as fd:
			lines = fd.read().splitlines()
		msg = "Read"
	except OSError as err:
		if err.errno != ENOENT:  # ENOENT - No such file or directory.
			print("[%s] Error %d: Unable to read lines from file '%s'!  (%s)" % (source, err.errno, filename, err.strerror))
		lines = default
		msg = "Default"
	if debug or forceDebug:
		length = len(lines) if lines else 0
		print("[%s] Line %d: %s %d lines from file '%s'." % (source, getframe(1).f_lineno, msg, length, filename))
	return lines


def fileWriteLines(filename, lines, source=DEFAULT_MODULE_NAME, debug=False):
	try:
		with open(filename, "w") as fd:
			if isinstance(lines, list):
				lines.append("")
				lines = "\n".join(lines)
			fd.write(lines)
		msg = "Wrote"
		result = 1
	except OSError as err:
		print("[%s] Error %d: Unable to write %d lines to file '%s'!  (%s)" % (source, err.errno, len(lines), filename, err.strerror))
		msg = "Failed to write"
		result = 0
	if debug or forceDebug:
		print("[%s] Line %d: %s %d lines to file '%s'." % (source, getframe(1).f_lineno, msg, len(lines), filename))
	return result


def main(session, **kwargs):
	session.open(CCcamInfoMain)


def sessionstart(reason, **kwargs):
	if reason == 0 and ecmInfoStart is None:
		CCcamPrioMaker.CCPrioMakerAutostart(kwargs["session"])
		# ecmInfoStart = ecmInfo.gotSession(kwargs["session"])
