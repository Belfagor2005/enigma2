#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# CCam Organizer by fsenes 2011
# modded by lululla 20240314
from Screens.Screen import Screen
from Components.MenuList import MenuList
from Components.ActionMap import ActionMap
from Screens.MessageBox import MessageBox
from Tools.Directories import fileExists

import gettext
_ = gettext.gettext


class OrganizerMenu(Screen):
	skin = """
		<screen position="center,center" size="460,400" title="CCcam Organizer" >
			<widget name="myMenu" position="10,10" size="420,380" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session):
		self.session = session
		listx = []
		if fileExists("/etc/CCcam.cfg"):
			listx.append((_("Delete Peer"), "two"))
			listx.append((_("Recover Peer"), "tree"))
			listx.append((_("Find Fakes"), "four"))
			listx.append((_("Stop Finding Fakes"), "five"))
		listx.append((_("Exit"), "exit"))

		Screen.__init__(self, session)
		self.setTitle(_("CCcam Organizer"))
		self["myMenu"] = MenuList(listx)
		self["myActionMap"] = ActionMap(["SetupActions"], {"ok": self.go, "cancel": self.cancel}, -2)

	def go(self):
		if not fileExists("/etc/CCcam.cfg"):
			return
		global returnValue
		returnValue = self["myMenu"].l.getCurrentSelection() and self["myMenu"].l.getCurrentSelection()[1]
		# if returnValue is "five":
		if returnValue == "five":
			self.Revert()
		# elif returnValue is "exit":
		elif returnValue == "exit":
			self.close(None)
		else:
			self.session.open(OrganizerNewmenu)

	def cancel(self):
		self.close(None)

	def Revert(self):
		lines = []
		try:
			with open("/etc/CCcam.cfg", "r") as f:
				for line in f:
					if line.startswith("#FC:"):
						line = line.replace("#FC:", "C:")
					lines.append(line)
			# Write the modified lines back to the file
			with open("/etc/CCcam.cfg", "w") as f:
				f.writelines(lines)

			self.session.open(MessageBox, _("\nSTOPPED FINDING FAKES \n\nREVERTED BACK TO INITIAL STATUS"), MessageBox.TYPE_INFO)
		except IOError as e:
			print("Error while accessing /etc/CCcam.cfg:", e)
			self.session.open(MessageBox, _("Failed to revert file: %s") % str(e), MessageBox.TYPE_ERROR)


class OrganizerNewmenu(Screen):
	skin = """
		<screen position="center,center" size="460,400" title="CCcam Organizer" >
			<widget name="Newmenu" position="10,10" size="420,380" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session):
		self.session = session
		self.CFG = "/etc/CCcam.cfg"
		if not fileExists(self.CFG):
			self.close()
			return

		self.find = ""
		self.replace = ""
		self.selected = ""

		menu_list = []
		try:
			with open(self.CFG, "r") as f:
				for line in f:
					# Per "two" o "four": linee valide normali
					if returnValue in ("two", "four") and (line.startswith("C:") or line.startswith("C :")):
						parts = line.split()
						if len(parts) > 1:
							menu_list.append((_(parts[1]), line))
					# Per "tree": linee commentate speciali
					elif returnValue == "tree" and (line.startswith("#!C:") or line.startswith("#!C :")):
						parts = line.split()
						if len(parts) > 1:
							menu_list.append((_(parts[1]), line))
		except IOError as e:
			print("Error reading file:", e)
			self.session.open(MessageBox, _("Error opening configuration file: %s") % str(e), MessageBox.TYPE_ERROR)
			self.close()

		Screen.__init__(self, session)
		self.setTitle(_("CCcam Organizer"))
		self["Newmenu"] = MenuList(menu_list)
		# if returnValue is "two":
		if returnValue == "two":
			self["Actions"] = ActionMap(["SetupActions"], {"ok": self.delete, "cancel": self.close}, -2)
		# elif returnValue is "tree":
		elif returnValue == "tree":
			self["Actions"] = ActionMap(["SetupActions"], {"ok": self.undelete, "cancel": self.close}, -2)
		# elif returnValue is "four":
		elif returnValue == "four":
			self["Actions"] = ActionMap(["SetupActions"], {"ok": self.FindFakes, "cancel": self.close}, -2)

	def delete(self):
		self.selected = self["Newmenu"].l.getCurrentSelection() and self["Newmenu"].l.getCurrentSelection()[1]
		if not self.selected:
			return
		self.findReplace("C:", "#!C:", self.selected)
		self.message(self.selected, _("Temporarely DELETED"))

	def undelete(self):
		if self["Newmenu"].l.getCurrentSelection() is not None:
			self.selected = self["Newmenu"].l.getCurrentSelection() and self["Newmenu"].l.getCurrentSelection()[1]
			if not self.selected:
				return
			self.findReplace("#!C:", "C:", self.selected)
			self.message(self.selected, _("UNDELETED"))
		else:
			self.selected = _("a NOTHING.TO.UNDELE")
			self.message(self.selected, _("PRESS RETURN"))

	def FindFakes(self):
		self.selected = self["Newmenu"].l.getCurrentSelection() and self["Newmenu"].l.getCurrentSelection()[1]
		if not self.selected:
			return

		lines = []
		try:
			with open(self.CFG, "r") as f:
				for line in f:
					if line.startswith("C:") and line != self.selected:
						line = line.replace("C:", "#FC:")
					lines.append(line)

			with open(self.CFG, "w") as f:
				f.writelines(lines)

			self.message(self.selected, _("Set as UNIQUE PEER"))
		except IOError as e:
			print("Error processing CCcam.cfg:", e)
			self.session.open(MessageBox, _("Error while editing configuration: %s") % str(e), MessageBox.TYPE_ERROR)

	def findReplace(self, find, replace, selected):
		lines = []
		try:
			with open(self.CFG, "r") as f:
				for line in f:
					if line.startswith(find) and line == selected:
						line = line.replace(find, replace)
					lines.append(line)

			with open(self.CFG, "w") as f:
				f.writelines(lines)
		except IOError as e:
			print("Error processing CCcam.cfg:", e)
			self.session.open(MessageBox, _("Error while editing configuration: %s") % str(e), MessageBox.TYPE_ERROR)

	def message(self, selected, text):
		try:
			msg = selected.split()[1]
			self.session.open(MessageBox, "\n%s \n\n%s" % (msg, text), MessageBox.TYPE_INFO)
		except:
			pass
