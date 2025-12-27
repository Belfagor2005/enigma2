# -*- coding: utf-8 -*-
# !/usr/bin/python

from os import listdir, makedirs, chmod, remove
from os.path import exists
import codecs
import subprocess
from random import choice
from requests import get, exceptions
import gettext
from enigma import eTimer
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Sources.List import List
from Screens.Console import Console
from Screens.Screen import Screen

_ = gettext.gettext


fps = "https://patbuweb.com/script/script.tar"

AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.102 Safari/537.36",
	"Mozilla/5.0 (iPhone; CPU iPhone OS 16_1_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:114.0) Gecko/20100101 Firefox/114.0",
	"Mozilla/5.0 (Windows NT 6.1; Trident/7.0; AS; en-US) like Gecko",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.5563.111 Safari/537.36 Edge/111.0.1661.62",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.131 Safari/537.36 Edge/92.0.902.67"
]

version = 'v.1.2'


class OpenScript(Screen):
	skin = """
		<screen name="OpenScript" position="center,center" size="1920,1080" Title="Acherone Script" backgroundColor="transparent" flags="wfNoBorder">
			<widget source="list" render="Listbox" position="56,151" size="838,695" font="Regular;34" itemHeight="50" scrollbarMode="showOnDemand" transparent="1" zPosition="5" foregroundColor="#00a0a0a0" foregroundColorSelected="#ffffff" backgroundColor="#20000000" backgroundColorSelected="#0b2049">
				<convert type="TemplatedMultiContent">
					{"template": [
						MultiContentEntryText(pos=(0, 0), size=(800, 50), font=0, flags=RT_HALIGN_LEFT, text=1),  # Script name
					],
					"fonts": [gFont("Regular", 34)],
					"itemHeight": 50}
				</convert>
			</widget>

			<widget name="line1" position="134,34" size="776,80" font="Regular;42" halign="center" valign="center" foregroundColor="yellow" backgroundColor="#202020" transparent="0" zPosition="1" />
			<widget name="description" position="42,856" size="877,141" font="Regular; 36" halign="center" valign="center" foregroundColor="yellow" backgroundColor="#202020" transparent="0" zPosition="1" />
			<widget font="Regular; 30" halign="right" position="1401,20" render="Label" size="500,40" source="global.CurrentTime" transparent="1">
				<convert type="ClockToText">Format:%a %d.%m. | %H:%M</convert>
			</widget>
			<eLabel backgroundColor="red" cornerRadius="3" position="34,1064" size="296,6" zPosition="11" />
			<eLabel backgroundColor="green" cornerRadius="3" position="342,1064" size="300,6" zPosition="11" />
			<eLabel backgroundColor="yellow" cornerRadius="3" position="652,1064" size="300,6" zPosition="11" />
			<widget name="key_red" render="Label" position="32,1016" size="300,45" zPosition="11" font="Regular; 30" valign="center" halign="center" backgroundColor="background" transparent="1" foregroundColor="white" />
			<widget name="key_green" render="Label" position="342,1016" size="300,45" zPosition="11" font="Regular; 30" valign="center" halign="center" backgroundColor="background" transparent="1" foregroundColor="white" />
			<widget name="key_yellow" render="Label" position="652,1016" size="300,45" zPosition="11" font="Regular; 30" valign="center" halign="center" backgroundColor="background" transparent="1" foregroundColor="white" />
			<eLabel backgroundColor="#002d3d5b" cornerRadius="20" position="0,0" size="1920,1080" zPosition="-99" />
			<eLabel backgroundColor="#001a2336" cornerRadius="30" position="20,1014" size="1880,60" zPosition="-80" />
			<eLabel name="" position="31,30" size="901,977" zPosition="-90" cornerRadius="18" backgroundColor="#00171a1c" foregroundColor="#00171a1c" />
			<widget source="session.VideoPicture" render="Pig" position="997,100" zPosition="19" size="880,499" backgroundColor="transparent" transparent="0" cornerRadius="14" />
		</screen>"""

	def __init__(self, session, args=None):
		Screen.__init__(self, session)
		self.session = session
		self['line1'] = Label(_('Available Scripts'))
		self['description'] = Label(_('Description:\n'))
		self['key_red'] = Label(_('Close'))
		self['key_green'] = Label(_('Select'))
		self['key_yellow'] = Label(_('Download'))
		self.mlist = []
		self['list'] = List(self.mlist)
		self['list'].onSelectionChanged.append(self.on_move)

		self.original_actions = {
			'ok': self.safe_select,
			'green': self.safe_select,
			'yellow': self.safe_download,
			'cancel': self.close,
			'red': self.close
		}

		self["actions"] = ActionMap(['OkCancelActions', 'ColorActions'],
									self.original_actions, -1)
		self.onShown.append(self.refresh_list)

	def refresh_list(self):
		try:
			if not exists('/usr/script'):
				makedirs('/usr/script', 493)
		except BaseException:
			pass

		myscripts = listdir('/usr/script')
		scripts = []
		for fil in myscripts:
			if fil.endswith('.sh'):
				fil2 = fil[:-3]
				myfil = '/usr/script/' + str(fil)
				desc = None
				with codecs.open(myfil, "rb", encoding="latin-1") as f:
					for line in f.readlines():
						line = line.strip()
						if line.startswith('#DESCRIPTION='):
							desc = line[13:]
							break
						elif line.startswith('##DESCRIPTION='):
							desc = line[14:]
							break

				if not desc:
					desc = _("%s") % fil2
				desc = desc.replace('_', ' ').replace('-', ' ').capitalize()
				scripts.append((fil2, desc))

		scripts.sort(key=lambda x: x[0].lower())
		self.mlist = scripts
		self['list'].setList(self.mlist)

	def getScrip(self, url):
		dest = "/tmp/script.tar"
		headers = {"User-Agent": choice(AGENTS)}

		try:
			response = get(url, headers=headers, timeout=(3.05, 6))
			response.raise_for_status()

			with open(dest, "wb") as file:
				file.write(response.content)

			# Clean old scripts
			subprocess.run(["rm", "-rf", "/usr/script/*"], check=True)
			# Extract new ones
			subprocess.run(["tar", "-xvf", dest, "-C", "/usr/script"], check=True)

			if exists(dest):
				remove(dest)

			self.refresh_list()
			self.show_temp_message(_("Scripts downloaded successfully!"), 3000)

		except exceptions.RequestException as error:
			print("Error during script download:", str(error))
			self.show_temp_message(_("Download error: %s") % str(error)[:50], 4000)

		except subprocess.CalledProcessError as e:
			print("Error during script extraction:", str(e))
			self.show_temp_message(_("Extraction error"), 4000)

		except Exception as e:
			print("Unexpected error:", str(e))
			self.show_temp_message(_("Unexpected error"), 4000)

	def safe_download(self):
		"""Download script pack"""

		def download_wrapper():
			self.getScrip(fps)

		self.show_confirm(_("Download Script Pack?"), download_wrapper)

	def safe_select(self):
		"""Select script"""
		if len(self.mlist) > 0:
			mysel = self['list'].getCurrent()
			if mysel:
				script_name = mysel[0]

				def execute_wrapper():
					self.execute_current_script()

				self.show_confirm(_("Execute %s?") % script_name, execute_wrapper)
		else:
			self.show_temp_message(_("Please Download Script first!"), 3000)

	def show_confirm(self, question, callback):
		"""Show confirmation dialog using existing interface"""
		# Save current state
		self.confirm_data = {
			'line1': self['line1'].getText(),
			'desc': self['description'].getText(),
			'callback': callback
		}

		# Show question
		self['line1'].setText(question)
		self['description'].setText(_("GREEN=Confirm, RED=Cancel"))

		# Change actions temporarily
		self["actions"].actions.update({
			'green': self.confirm_yes,
			'red': self.confirm_no,
			'ok': self.confirm_yes,
			'cancel': self.confirm_no,
			'yellow': None  # Disable yellow during confirmation
		})

		# Auto-restore timer (10 seconds)
		self.confirm_timer = eTimer()
		self.confirm_timer.callback.append(self.confirm_no)
		self.confirm_timer.start(10000, True)

	def confirm_yes(self):
		"""Confirm yes - execute callback"""
		if hasattr(self, 'confirm_data') and self.confirm_data['callback']:
			# Restore interface first
			self['line1'].setText(_("Processing..."))
			self['description'].setText("")

			# Execute callback
			self.confirm_data['callback']()

		# Cleanup
		self.confirm_cleanup()

	def confirm_no(self):
		"""Confirm no - check if user wants to exit"""
		# If we have confirmation data, we're just canceling an operation
		if hasattr(self, 'confirm_data'):
			self.confirm_cleanup()
		else:
			# No confirmation data = user pressed RED to exit
			self.confirm_cleanup(close_plugin=True)

	def confirm_cleanup(self, close_plugin=False):
		"""Cleanup after confirmation - optional plugin close"""
		# Restore original state
		if hasattr(self, 'confirm_data'):
			self['line1'].setText(self.confirm_data['line1'])
			self['description'].setText(self.confirm_data['desc'])

		# Restore original actions
		self["actions"].actions.update(self.original_actions)

		# Stop timer if exists
		if hasattr(self, 'confirm_timer'):
			self.confirm_timer.stop()

		# Clean attributes
		for attr in ['confirm_data', 'confirm_timer']:
			if hasattr(self, attr):
				delattr(self, attr)

		# Close plugin if requested
		if close_plugin:
			self.close()

	def execute_current_script(self):
		"""Execute currently selected script"""
		if len(self.mlist) > 0:
			mysel = self['list'].getCurrent()
			if mysel:
				mysel = mysel[0]
				mysel2 = '/usr/script/' + mysel + '.sh'
				try:
					chmod(mysel2, 0o0777)
					mytitle = _("Script Executor %s") % mysel
					self.session.open(Console, title=mytitle, cmdlist=[mysel2])
				except Exception as e:
					self.show_temp_message(_("Error: %s") % str(e)[:50], 3000)

	def show_temp_message(self, message, duration=2000):
		"""Show temporary message"""
		old_line1 = self['line1'].getText()
		old_desc = self['description'].getText()

		self['line1'].setText(message)
		self['description'].setText("")

		# Timer to restore
		timer = eTimer()
		timer.callback.append(lambda: (
			self['line1'].setText(old_line1),
			self['description'].setText(old_desc)
		))
		timer.start(duration, True)

	def on_move(self):
		mysel = self['list'].getCurrent()
		if mysel:
			mytext = ' ' + mysel[1]
			self['description'].setText(str(mytext))
		else:
			self["description"].setText(_("Script Executor %s") % version)
