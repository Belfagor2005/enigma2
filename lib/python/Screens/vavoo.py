#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
****************************************
*        coded by Lululla              *
*             11/02/2025               *
* thank's to @oktus for image screen   *
****************************************
# ---- thank's Kiddac for infinity support ---- #
# Info Linuxsat-support.com & corvoboys.org
"""

from Components.ActionMap import ActionMap
from Components.SelectionList import SelectionList, SelectionEntryComponent
from Components.Sources.StaticText import StaticText
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigText, configfile
from Screens.MessageBox import MessageBox
from Screens.Screen import Screen, ScreenSummary
from enigma import eDVBDB, eTimer
from os import makedirs as os_makedirs, path as os_path, remove as os_remove, popen
from requests import get, exceptions
from shutil import rmtree
from time import time
import json

from random import choice
from re import split, sub
from sys import version_info
from unicodedata import normalize
import requests

import gettext
_ = gettext.gettext

PY2 = False
PY3 = False
PY2 = version_info[0] == 2
PY3 = version_info[0] == 3


group_titles = {
    "Albania": "Albania",
    "Arabia": "Arabia",
    "Balkans": "Balkans",
    "Bulgaria": "Bulgaria",
    "France": "France",
    "Germany": "Germany",
    "Italy": "Italy",
    "Netherlands": "Netherlands",
    "Poland": "Poland",
    "Portugal": "Portugal",
    "Romania": "Romania",
    "Russia": "Russia",
    "Spain": "Spain",
    "Turkey": "Turkey",
    "United Kingdom": "United Kingdom"
}


try:
    from urllib import unquote
except ImportError:
    from urllib.parse import unquote


try:
    import pickle
except BaseException:
    from six.moves import cPickle as pickle


config.plugins.vavoomaker = ConfigSubsection()
choices = {"country": _("country")}
config.plugins.vavoomaker.current = ConfigSelection(choices=[(x[0], x[1]) for x in choices.items()], default=list(choices.keys())[0])
for ch in choices:
    setattr(config.plugins.vavoomaker, ch, ConfigText("", False))


class vavooFetcher():
    def __init__(self):
        self.tempDir = "/tmp/vavoo"
        os_makedirs(self.tempDir, exist_ok=True)
        self.cachefile = "/tmp/vavoo.cache"
        self.playlists = {"country": "https://vavoo.to/channels"}
        self.bouquetFilename = "userbouquet.vavoo.%s.tv"
        self.bouquetName = _("vavoo")
        self.playlists_processed = {key: {} for key in self.playlists.keys()}
        self.cache_updated = False
        if os_path.exists(self.cachefile):
            try:
                mtime = os_path.getmtime(self.cachefile)
                if mtime < time() - 86400:  # if file is older than one day delete it
                    os_remove(self.cachefile)
                else:
                    with open(self.cachefile, 'rb') as cache_input:
                        self.playlists_processed = pickle.load(cache_input)
            except Exception as e:
                print("[vavoo plugin] failed to open cache file", e)

    def downloadPage(self):
        os_makedirs(self.tempDir, exist_ok=True)
        link = self.playlists[config.plugins.vavoomaker.current.value]
        try:
            response = get(link, timeout=2.50)
            response.raise_for_status()
            with open(self.tempDir + "/" + config.plugins.vavoomaker.current.value, "wb") as f:
                f.write(response.content)
        except exceptions.RequestException as error:
            print("[vavoo plugin] failed to download", link)
            print("[vavoo plugin] error", str(error))

    def getPlaylist(self):
        current = self.playlists_processed[config.plugins.vavoomaker.current.value]
        if not current:

            self.downloadPage()

            known_urls = []

            json_data = self.tempDir + "/" + config.plugins.vavoomaker.current.value
            try:
                with open(json_data, encoding='utf-8', errors="ignore") as f:
                    playlist = json.load(f)
                    print("Tipo di playlist:", type(playlist), playlist)  # Debug
            except json.JSONDecodeError as e:
                print("Errore nel parsing del JSON:", e)
                playlist = []

            # If `playlist` is a dictionary, we turn it into a list
            if isinstance(playlist, dict):
                playlist = [playlist]

            for entry in playlist:
                if not isinstance(entry, dict):  # check ;)
                    print("no valid format :", entry)
                    continue

                # print("Processing entry:", entry)  # Debug
                country = unquote(entry.get("country", "")).strip("\r\n")
                name = unquote(entry.get("name", "")).strip("\r\n")
                name = decodeHtml(name)
                name = rimuovi_parentesi(name)
                ids = str(entry.get("id", "")).replace(':', '').replace(' ', '').replace(',', '')

                if not country or not name or not ids:
                    print("Dati mancanti in entry:", entry)
                    continue

                url = 'https://vavoo.to/live2/play/' + ids + '.ts'

                if url not in known_urls:
                    if country not in current:
                        current[country] = []
                    current[country].append((name, url))
                    known_urls.append(url)

            self.cache_updated = True

    def createBouquet(self, enabled):
        sig = getAuthSignature()
        app = '?n=1&b=5&vavoo_auth=%s#User-Agent=VAVOO/2.6' % (str(sig))
        current = self.playlists_processed[config.plugins.vavoomaker.current.value]
        for country in sorted([k for k in current.keys() if k in enabled], key=lambda x: group_titles.get(x, x).lower()):

            bouquet_list = []

            if current[country]:  # country not empty (how could it be)
                bouquet_list.append("1:64:0:0:0:0:0:0:0:0:%s" % group_titles.get(country, country))

                for channelname, url in sorted(current[country]):
                    url = url.strip() + str(app)
                    bouquet_list.append("4097:0:1:1:1:1:CCCC0000:0:0:0:%s:%s" % (url.replace(":", "%3a"), channelname))

            if bouquet_list:
                bouquet_filename = sanitizeFilename(country).replace(" ", "_").strip().lower()
                duplicated_translation = list(group_titles.values()).count(group_titles.get(country, country)) > 1
                bouquet_display_name = "%s - %s" % (self.bouquetName, group_titles.get(country, country))

                if duplicated_translation:
                    bouquet_display_name += " - " + choices[config.plugins.vavoomaker.current.value]

                eDVBDB.getInstance().addOrUpdateBouquet(
                    bouquet_display_name,
                    self.bouquetFilename % bouquet_filename,
                    bouquet_list,
                    False
                )

    def removeBouquet(self):
        current = self.playlists_processed[config.plugins.vavoomaker.current.value]
        for country in sorted([k for k in current.keys()], key=lambda x: str(group_titles.get(x, x)).lower()):
            if current[country]:
                bouquet_filename = sanitizeFilename(country).replace(" ", "_").strip().lower()
                bouquet_name = "userbouquet.vavoo.%s.tv" % bouquet_filename
                bouquet_path = os_path.join("/etc/enigma2", bouquet_name)

                if os_path.exists(bouquet_path):
                    print("[vavoo plugin] Removing bouquet:", bouquet_name)
                    eDVBDB.getInstance().removeBouquet(bouquet_name)
                else:
                    print("[vavoo plugin] Bouquet does not exist:", bouquet_name)

        eDVBDB.getInstance().reloadBouquets()

    def cleanup(self):
        rmtree(self.tempDir)
        if self.cache_updated:
            with open(self.cachefile, 'wb') as cache_output:
                pickle.dump(self.playlists_processed, cache_output, pickle.HIGHEST_PROTOCOL)


class VavooScreen(Screen):
    def __init__(self, session):
        Screen.__init__(self, session)
        self.title = _("vavoo playlists") + " - " + choices.get(config.plugins.vavoomaker.current.value, config.plugins.vavoomaker.current.value).title()
        self.skinName = ["Setup"]
        self.enabled = []
        self.process_build = []
        self.vavooFetcher = vavooFetcher()
        self["config"] = SelectionList([], enableWrapAround=True)
        self["key_red"] = StaticText(_("Cancel"))
        self["key_green"] = StaticText(_("Create bouquets"))
        self["key_yellow"] = StaticText(_("Toggle all"))
        self["key_blue"] = StaticText(_("Remove"))
        self["description"] = StaticText("")
        self["actions"] = ActionMap(
            [
                "SetupActions",
                "ColorActions"
            ],
            {
                "ok": self["config"].toggleSelection,
                "save": self.makeBouquets,
                "cancel": self.backCancel,
                "yellow": self["config"].toggleAllSelection,
                "blue": self.deleteBouquets,
            },
            -2
        )
        self.loading_message = _("Downloading playlist - Please wait!")
        self["description"].text = self.loading_message

        self.onClose.append(self.__onClose)

        self.timer = eTimer()
        if hasattr(self.timer, "callback"):
            self.timer.callback.append(self.buildList)
        else:
            if os_path.exists("/usr/bin/apt-get"):
                self.timer_conn = self.timer.timeout.connect(self.buildList)
            print("[Version Check] ERROR: eTimer does not support callback.append()")
        self.timer.start(10, 1)

    def __onClose(self):
        self.vavooFetcher.cleanup()

    def buildList(self):
        self["actions"].setEnabled(False)
        self.vavooFetcher.getPlaylist()
        self.process_build = sorted(list(self.vavooFetcher.playlists_processed[config.plugins.vavoomaker.current.value].keys()), key=lambda x: group_titles.get(x, x).lower())
        self.enabled = [x for x in getattr(config.plugins.vavoomaker, config.plugins.vavoomaker.current.value).value.split("|") if x in self.process_build]
        self["config"].setList([SelectionEntryComponent(group_titles.get(x, x), x, "", x in self.enabled) for x in self.process_build])
        self["actions"].setEnabled(True)
        self["description"].text = ""

    def readList(self):
        self.enabled = [x[0][1] for x in self["config"].list if x[0][3]]
        getattr(config.plugins.vavoomaker, config.plugins.vavoomaker.current.value).value = "|".join(self.enabled)

    def makeBouquets(self):
        self.readList()
        if self.enabled:
            self["actions"].setEnabled(False)
            self.title += " - " + _("Creating bouquets")
            self["description"].text = _("Creating bouquets. This may take some time. Please be patient.")
            self["key_red"].text = ""
            self["key_green"].text = ""
            self["key_yellow"].text = ""
            self["key_blue"].text = ""
            self["config"].setList([])
            config.plugins.vavoomaker.current.save()
            for ch in choices:
                getattr(config.plugins.vavoomaker, ch).save()
            configfile.save()
            self.runtimer = eTimer()
            if hasattr(self.runtimer, "callback"):
                self.runtimer.callback.append(self.doRun)
            else:
                if os_path.exists("/usr/bin/apt-get"):
                    self.runtimer_conn = self.runtimer.timeout.connect(self.doRun)
                print("[Version Check] ERROR: eTimer does not support callback.append()")
            self.runtimer.start(10, 1)
        else:
            self.session.open(MessageBox, _("Please select the bouquets you wish to create"))

    def doRun(self):
        self.vavooFetcher.createBouquet(self.enabled)
        self.close()

    def backCancel(self):
        self.readList()
        if any([getattr(config.plugins.vavoomaker, choice).isChanged() for choice in choices]):
            self.session.openWithCallback(self.cancelConfirm, MessageBox, _("Really close without saving settings?"))
        else:
            self.close()

    def deleteBouquets(self):

        def onConfirm(answer):
            if answer:
                self.vavooFetcher.removeBouquet()
                self.session.open(MessageBox, _("Vavoo Favorite Bouquet removed."), MessageBox.TYPE_INFO, timeout=5)
            else:
                self.session.open(MessageBox, _("Operation cancelled or Vavoo Favorite Bouquet does not exist."), MessageBox.TYPE_INFO, timeout=5)

        self.session.openWithCallback(
            onConfirm,
            MessageBox,
            _("Remove Vavoo Favorite Bouquet?"),
            MessageBox.TYPE_YESNO,
            timeout=5,
            default=True
        )

    def cancelConfirm(self, result):
        if not result:
            return
        config.plugins.vavoomaker.current.cancel()
        for ch in choices:
            getattr(config.plugins.vavoomaker, ch).cancel()
        self.close()

    def createSummary(self):
        return PluginSummary


class PluginSummary(ScreenSummary):
    def __init__(self, session, parent):
        ScreenSummary.__init__(self, session, parent=parent)
        self.skinName = "PluginBrowserSummary"
        self["entry"] = StaticText("")
        if self.addSelect not in self.onShow:
            self.onShow.append(self.addSelect)
        if self.removeSelect not in self.onHide:
            self.onHide.append(self.removeSelect)

    def addSelect(self):
        if self.selectionChanged not in self.parent["config"].onSelectionChanged:
            self.parent["config"].onSelectionChanged.append(self.selectionChanged)
        self.selectionChanged()

    def removeSelect(self):
        if self.selectionChanged in self.parent["config"].onSelectionChanged:
            self.parent["config"].onSelectionChanged.remove(self.selectionChanged)

    def selectionChanged(self):
        item = self.parent["config"].getCurrent()
        self["entry"].text = item[0][0] if item else ""


def decodeHtml(text):
    if PY3:
        import html
        text = html.unescape(text)
    else:
        from six.moves import html_parser
        h = html_parser.HTMLParser()
        text = h.unescape(text.decode('utf8')).encode('utf8')

    html_replacements = {
        '&amp;': '&', '&apos;': "'", '&lt;': '<', '&gt;': '>', '&ndash;': '-',
        '&quot;': '"', '&ntilde;': '~', '&rsquo;': "'", '&nbsp;': ' ',
        '&equals;': '=', '&quest;': '?', '&comma;': ',', '&period;': '.',
        '&colon;': ':', '&lpar;': '(', '&rpar;': ')', '&excl;': '!',
        '&dollar;': '$', '&num;': '#', '&ast;': '*', '&lowbar;': '_',
        '&lsqb;': '[', '&rsqb;': ']', '&half;': '1/2', '&DiacriticalTilde;': '~',
        '&OpenCurlyDoubleQuote;': '"', '&CloseCurlyDoubleQuote;': '"'
    }

    for key, val in html_replacements.items():
        text = text.replace(key, val)
    return text.strip()


def rimuovi_parentesi(testo):
    return sub(r'\s*\([^)]*\)\s*', ' ', testo).strip()


def sanitizeFilename(filename):
    """Return a fairly safe version of the filename.

    We don't limit ourselves to ascii, because we want to keep municipality
    names, etc, but we do want to get rid of anything potentially harmful,
    and make sure we do not exceed Windows filename length limits.
    Hence a less safe blacklist, rather than a whitelist.
    """
    blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0", "(", ")", " "]
    reserved = [
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
        "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
        "LPT6", "LPT7", "LPT8", "LPT9",
    ]  # Reserved words on Windows
    filename = "".join(c for c in filename if c not in blacklist)
    # Remove all charcters below code point 32
    filename = "".join(c for c in filename if 31 < ord(c))
    filename = normalize("NFKD", filename)
    filename = filename.rstrip(". ")  # Windows does not allow these at end
    filename = filename.strip()
    if all([x == "." for x in filename]):
        filename = "__" + filename
    if filename in reserved:
        filename = "__" + filename
    if len(filename) == 0:
        filename = "__"
    if len(filename) > 255:
        parts = split(r"/|\\", filename)[-1].split(".")
        if len(parts) > 1:
            ext = "." + parts.pop()
            filename = filename[:-len(ext)]
        else:
            ext = ""
        if filename == "":
            filename = "__"
        if len(ext) > 254:
            ext = ext[254:]
        maxl = 255 - len(ext)
        filename = filename[:maxl]
        filename = filename + ext
        filename = filename.rstrip(". ")
        if len(filename) == 0:
            filename = "__"
    return filename


def get_external_ip():
    try:
        return popen('curl -s ifconfig.me').readline().strip()
    except BaseException:
        pass
    try:
        return requests.get('https://v4.ident.me').text.strip()
    except BaseException:
        pass
    try:
        return requests.get('https://api.ipify.org').text.strip()
    except BaseException:
        pass
    try:
        return requests.get('https://api.myip.com/').json().get("ip", "")
    except BaseException:
        pass
    try:
        return requests.get('https://checkip.amazonaws.com').text.strip()
    except BaseException:
        pass
    return None


def convert_to_unicode(data):
    """
    In Python 3 le stringhe sono già Unicode, quindi:
    - Se data è bytes, decodificalo.
    - Se è str, restituiscilo così com'è.
    """
    if isinstance(data, bytes):
        return data.decode('utf-8')
    elif isinstance(data, str):
        return data  # Già Unicode in Python 3
    elif isinstance(data, dict):
        return {convert_to_unicode(k): convert_to_unicode(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_unicode(item) for item in data]
    return data


def set_cache(key, data, timeout):
    """Salva i dati nella cache."""
    file_path = os_path.join('/usr/vavoo', key + '.json')
    try:
        with open(file_path, 'w', encoding='utf-8') as cache_file:
            # Salviamo i dati convertiti in Unicode (in pratica, rimane invariato in Python 3)
            json.dump(convert_to_unicode(data), cache_file, indent=4)
    except Exception as e:
        print("Error saving cache:", e)


def get_cache(key):
    file_path = os_path.join('/usr/vavoo', key + '.json')
    if os_path.exists(file_path) and os_path.getsize(file_path) > 0:
        try:
            with open(file_path, 'r', encoding='utf-8') as cache_file:
                data = json.load(cache_file)
                # Verifica se il cache è ancora valido
                if data.get('sigValidUntil', 0) > int(time.time()):
                    if data.get('ip', "") == get_external_ip():
                        return data.get('value')
        except ValueError as e:
            print("Error decoding JSON from", file_path, ":", e)
        except Exception as e:
            print("Unexpected error reading cache file {}:".format(file_path), e)
        os_remove(file_path)
    return None


def getAuthSignature():
    signfile = get_cache('signfile')
    if signfile:
        return signfile

    veclist = get_cache("veclist")
    if not veclist:
        veclist = requests.get("https://raw.githubusercontent.com/Belfagor2005/vavoo/refs/heads/main/data.json").json()
        set_cache("veclist", veclist, timeout=3600)

    sig = None
    i = 0
    while not sig and i < 50:
        i += 1
        vec = {"vec": choice(veclist)}
        req = requests.post('https://www.vavoo.tv/api/box/ping2', data=vec).json()
        sig = req.get('signed') or req.get('data', {}).get('signed') or req.get('response', {}).get('signed')

    if sig:
        set_cache('signfile', convert_to_unicode(sig), timeout=3600)
    return sig


def PluginMain(session, **kwargs):
    return session.open(VavooScreen)
