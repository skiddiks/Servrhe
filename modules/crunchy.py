# -*- coding: utf-8 -*-
dependencies = []

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from twisted.internet.utils import getProcessOutputAndValue
from twisted.web.client import CookieAgent, RedirectAgent, FileBodyProducer
from twisted.web.http_headers import Headers

from crypto.cipher.aes_cbc import AES_CBC
from crypto.cipher.base import noPadding

from array import array
from binascii import hexlify, unhexlify
from collections import namedtuple
from bs4 import BeautifulSoup, UnicodeDammit
from datetime import datetime
from StringIO import StringIO

import base64, codecs, cookielib, json, math, os, sha, shutil, time, urllib, urlparse, uuid, zlib, treq

dependencies = ["config", "utils", "commands", "flv", "ftp", "showtimes"]

ShowObject = namedtuple("CrunchyShowObject",["name", "episodes"])
EpisodeObject = namedtuple("CrunchyEpisodeObject",["series", "episode", "title", "duration", "airtime", "link", "media_id"])

player_revision = '20130531153222.a6d69c63cc5ec3d72835f991b7d014be'
qualities = {'360':("106","60"), '480':("106","61"), '720':("106","62"), '1080':("108","80")}
xml_url = "http://www.crunchyroll.com/xml/?req=RpcApiVideoPlayer_GetStandardConfig&media_id={}&video_format={}&video_quality={}&auto_play=1&aff=crunchyroll-website&show_pop_out_controls=1&pop_out_disable_message="
swf_url = "http://static.ak.crunchyroll.com/flash/"

def spliceContents(video, subs):
    if video and subs:
        return "video and subs"
    elif video:
        return "video"
    elif subs:
        return "subs"
    else:
        return "nothing"

def createString(length, modulo, first, second):
    string = ""
    bytes = [first, second]
    for _ in range(length):
        next = bytes[-2] + bytes[-1]
        bytes.append(next)
        string += chr(next % modulo + 33)
    return string

def generateKey(mediaid, size = 32):
    # Below: Do some black magic
    eq1 = int(int(math.floor(math.sqrt(6.9) * math.pow(2, 25))) ^ mediaid)
    eq2 = int(math.floor(math.sqrt(6.9) * math.pow(2, 25)))
    eq3 = (mediaid ^ eq2) ^ (mediaid ^ eq2) >> 3 ^ eq1 * 32
    # Below: Creates a 160-bit SHA1 hash 
    shaHash = sha.new(createString(20, 97, 1, 2) + str(eq3)) 
    finalHash = shaHash.digest()
    hashArray = array("B", finalHash)
    # Below: Pads the 160-bit hash to 256-bit using zeroes, incase a 256-bit key is requested
    if size > len(hashArray):
        padding = [0] * (size - len(hashArray))
        hashArray.extend(padding)
    return hashArray.tostring()[:size]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("crunchy")
        self.agent = CookieAgent(master.agent, cookielib.CookieJar())
        self.shows = {}
        self.cache_loop = None
        self.logged_in = False
        self.start()

    @inlineCallbacks
    def start(self):
        yield self.login()
        self.cache_loop = LoopingCall(self.cache)
        self.cache_loop.start(900)

    def stop(self):
        if self.cache_loop is not None and self.cache_loop.running:
            self.cache_loop.stop()
            self.cache_loop = None

    @inlineCallbacks
    def login(self):
        self.logged_in = False
        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")

        url = 'https://www.crunchyroll.com/?a=formhandler'
        headers = Headers({
            'Content-Type': ['application/x-www-form-urlencoded'],
            'Referer': ['https://www.crunchyroll.com'],
            'User-Agent': ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:17.0) Gecko/17.0 Firefox/17.0']
        })
        data = FileBodyProducer(StringIO(urllib.urlencode({
            'formname': 'RpcApiUser_Login',
            'next_url': '',
            'fail_url': '/login',
            'name': user,
            'password': passwd
        })))
        response = yield self.agent.request("POST", url, headers, data)

        self.logged_in = True

    @inlineCallbacks
    def cache(self):
        if not self.logged_in:
            return

        body = ""
        for PAGE in range(3): # Pages 0, 1, 2 - Should be plenty
            response = yield self.agent.request("GET","http://www.crunchyroll.com/videos/anime/simulcasts/ajax_page?pg={:d}".format(PAGE))
            body += yield self.master.modules["utils"].returnBody(response)
        soup = BeautifulSoup(body, from_encoding="utf8")
        epoch = datetime(1970,1,1)

        shows = {}
        deferreds = []
        for element in soup("a", token="shows-portraits"):
            key = element["href"].lstrip("/")
            name = element["title"]
            shows[name] = {}

            response = yield self.agent.request("GET", "http://www.crunchyroll.com/{}.rss".format(key))
            body = yield self.master.modules["utils"].returnBody(response)
            xml = BeautifulSoup(body, "xml", from_encoding="utf8")

            for item in xml("item"):
                airtime = item.find("premiumPubDate")
                episode = item.find("episodeNumber")
                title = item.find("episodeTitle")
                duration = item.find("duration")
                link = item.find("link")
                media_id = item.find("mediaId")

                if not airtime or not episode or not link or not media_id:
                    continue

                airtime = int((datetime.strptime(airtime.string, "%a, %d %b %Y %H:%M:%S %Z") - epoch).total_seconds())
                try:
                    e = int(episode.string)
                    key = "{:02d}".format(e)
                except:
                    key = episode.string
                    e = 0
                episode = e
                title = title.string if title and title.string else u""
                duration = int(duration.string) if duration else 0
                link = link.string
                media_id = media_id.string

                duration = "{:d}:{:02d}".format(duration / 60, duration % 60)

                if not link or not media_id:
                    continue

                shows[name][key] = {
                    "series": name,
                    "episode": episode,
                    "title": title,
                    "duration": duration,
                    "airtime": airtime,
                    "link": link,
                    "media_id": media_id
                }

        for series, episodes in shows.items():
            if series not in self.shows:
                self.log(u"Found {} (Series) [{:,d} episodes]", series, len(shows[series]))
                continue
            for episode, show in episodes.items():
                if episode not in self.shows[series]:
                    self.log(u"Found {} #{}", series, episode)
                elif self.shows[series][episode] != show:
                    self.log(u"Updated {} #{}", series, episode)

        self.shows = shows

    def resolve(self, name):
        exception = self.master.modules["commands"].exception
        matches = []
        if not name:
            raise exception(u"Show name not specified.")
        name = name.lower()
        for s in self.shows.keys():
            if s.lower() == name:
                return self.nameToObject(s)
            if s.lower().count(name):
                matches.append(s)
        if len(matches) > 1:
            if len(matches) > 5:
                extra = "and {:d} more.".format(len(matches) - 5)
                matches = matches[:5] + [extra]
            raise exception(u"Show name not specific, found: {}".format(u", ".join(matches)))
        elif not matches:
            raise exception(u"Show name not found.")
        return self.nameToObject(matches[0])

    def nameToObject(self, name):
        if name not in self.shows:
            return None
        data = self.shows[name]
        episodes = {}
        for k, v in data.items():
            episodes[k] = EpisodeObject(**v)
        return ShowObject(name, episodes)

    @inlineCallbacks
    def rip(self, guid, show, quality, video, subs):
        exception = self.master.modules["commands"].exception

        if not self.logged_in:
            raise exception(u"Not logged in to CrunchyRoll")

        if quality not in qualities:
            raise exception(u"Invalid quality, must be one of: {}".format(u", ".join(qualities.keys())))

        filename = u"[CR] {} - {:02d} [{}p]".format(show.series, show.episode, quality).replace(u":", u"：").replace(u"/", u" \u2044 ")

        format = qualities[quality]
        url = xml_url.format(show.media_id, format[0], format[1])
        headers = Headers({
            'Content-Type': ['application/x-www-form-urlencoded'],
            'Referer': ['https://www.crunchyroll.com'],
            'User-Agent': ['Mozilla/5.0 (Macintosh; Intel Mac OS X 10.8; rv:17.0) Gecko/17.0 Firefox/17.0']
        })
        data = FileBodyProducer(StringIO(urllib.urlencode({
            'current_page': show.link
        })))
        response = yield self.agent.request("POST", url, headers, data)
        xml = yield self.master.modules["utils"].returnBody(response)

        soup = BeautifulSoup(xml, from_encoding="utf8")
        player_url = soup.find('default:chromelessplayerurl').string
        stream_info = soup.find('stream_info')
        subtitles = soup.find('subtitles')

        if not stream_info:
            raise exception(u"Could not parse XML")

        stream = {}
        stream['url'] = stream_info.host.string
        stream['token'] = stream_info.token.string
        stream['file'] = stream_info.file.string
        stream['swf_url'] = swf_url+player_revision+"/"+player_url

        if subs:
            if not subtitles:
                raise exception(u"Could not find subtitles")

            decoded = Decoder(xml)
            formatted = decoded.fancy

            with open(os.path.join(guid, filename.encode("utf8") + ".ass"), 'wb') as subfile:
                subfile.write(codecs.BOM_UTF8)
                subfile.write(formatted.encode('utf-8'))

            yield self.master.modules["ftp"].put(guid, filename+".ass")

        if video:
            parsed_url = urlparse.urlparse(stream['url'])

            if parsed_url.netloc.endswith("fplive.net"):
                ### START NEW CDN RIP & CONVERT ###
                inner_path, _, args = parsed_url.path.partition("?")
                
                if not args and parsed_url.query:
                    args = parsed_url.query
                elif parsed_url.query:
                    args += "&" + parsed_url.query

                ddl_url = "http://v.lvlt.crcdn.net{}/{}?{}".format(inner_path, stream['file'][4:], args)

                response = yield self.agent.request("GET", ddl_url)
                if response.code != 200:
                    self.log(u"DDL URL: {}".format(ddl_url))
                    self.log(u"RESPONSE CODE: {:d}".format(response.code))
                    raise exception(u"Failed to download FLV")

                try:
                    with open(os.path.join(guid, filename.encode("utf8") + '.mp4'), "wb") as f:
                        yield treq.collect(response, f.write)
                except Exception as e:
                    self.err(u"Failed to download FLV")
                    raise exception(u"Failed to download FLV")

                mkvmergeargs = ["-o", os.path.join(guid, filename.encode("utf8") + ".mkv"), os.path.join(guid, filename.encode("utf8") + ".mp4")]

                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("mkvmerge"), args=mkvmergeargs, env=os.environ)
                if code == 2:
                    raise exception(u"Failed to mux MKV")

                ### END NEW CDN RIP & CONVERT ###

            else:
                ### START OLD CDN RIP & CONVERT ###
                rtmpargs = ["-e", "-r", stream['url'], "-y", stream['file'], "-W", stream['swf_url'], "-T", stream['token'], "-o", os.path.join(guid, filename.encode("utf8") + '.flv')]

                retries = 15
                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("rtmpdump"), args=rtmpargs, env=os.environ)
                while code == 2 and retries:
                    retries -= 1
                    out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("rtmpdump"), args=rtmpargs, env=os.environ)
                if code != 0:
                    self.log(u"RTMPDUMP CMDLINE:\nrtmpdump " + u" ".join(rtmpargs))
                    self.log(u"RTMPDUMP STDOUT:\n" + out)
                    self.log(u"RTMPDUMP STDERR:\n" + err)
                    raise exception(u"Failed to download FLV")

                try:
                    self.master.modules["flv"].FLVFile(os.path.join(guid, filename.encode("utf8") + ".flv")).ExtractStreams(True, True, True, True)
                except:
                    self.err(u"FLVFile failed to extract streams")
                    raise exception(u"Failed to extract streams from FLV")
                    
                mkvmergeargs = ["-o", os.path.join(guid, filename.encode("utf8") + ".mkv"),
                    "--forced-track","0:yes","--compression","0:none","--timecodes","0:"+os.path.join(guid, filename.encode("utf8") + ".txt"),"-d","0","-A","-S",os.path.join(guid, filename.encode("utf8") + ".264"),
                    "--forced-track","0:yes","-a","0","-D","-S",os.path.join(guid, filename.encode("utf8") + ".aac")]

                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("mkvmerge"), args=mkvmergeargs, env=os.environ)
                if code == 2:
                    raise exception(u"Failed to mux MKV")

                ### END OLD CDN RIP & CONVERT ###

            yield self.master.modules["ftp"].put(guid, filename+".mkv")
        
        yield self.master.modules["ftp"].upload()

class Decoder(object):
    def __init__(self, xml=None, compressed=True):
        if xml is None:
            return

        self.id, self.iv, self.data = self.strain(xml)
        self.plain = self.decode(self.id, self.iv, self.data, compressed)
        self.fancy = self.format(self.plain)
        
    def strain(self, xml):
        soup = BeautifulSoup(xml, from_encoding="utf8")
        subtitle = soup.find('subtitle', attrs={'link': None})
        if subtitle:
            _id = int(subtitle['id'])
            _iv = subtitle.find('iv').contents[0]
            _data = subtitle.data.string
            return _id, _iv, _data

    def decode(self, id, iv, data, compressed=True):
        key = generateKey(id)
        iv = base64.b64decode(iv)
        data = base64.b64decode(data)
        data = iv + data
        cipher = AES_CBC(key, padding=noPadding(), keySize=32)
        decryptedData = cipher.decrypt(data)
        
        if compressed:
            return zlib.decompress(decryptedData)
        else:
            return decryptedData
            
    def format(self, script):
        dammit = UnicodeDammit.detwingle(script)
        soup = BeautifulSoup(dammit, from_encoding="utf8")
        header = soup.find('subtitle_script')
        header = "[Script Info]\nTitle: "+header['title']+"\nScriptType: v4.00+\nWrapStyle: "+header['wrap_style']+"\nPlayResX: 624\nPlayResY: 366\nScaledBorderAndShadow: yes\nYCbCr Matrix: TV.709\n\n";
        styles = "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n";
        events = "\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n";
        stylelist = soup.findAll('style')
        eventlist = soup.findAll('event')
        
        for style in stylelist:
            styles += "Style: " + style['name'] + "," + style['font_name'] + "," + style['font_size'] + "," + style['primary_colour'] + "," + style['secondary_colour'] + "," + style['outline_colour'] + "," + style['back_colour'] + "," + style['bold'] + "," + style['italic'] + "," + style['underline'] + "," + style['strikeout'] + "," + style['scale_x'] + "," + style['scale_y'] + "," + style['spacing'] + "," + style['angle'] + "," + style['border_style'] + "," + style['outline'] + "," + style['shadow'] + "," + style['alignment'] + "," + style['margin_l'] + "," + style['margin_r'] + "," + style['margin_v'] + "," + style['encoding'] + "\n"

        for event in eventlist:
            events += "Dialogue: 0,"+event['start']+","+event['end']+","+event['style']+","+event['name']+","+event['margin_l']+","+event['margin_r']+","+event['margin_v']+","+event['effect']+","+event['text']+"\n"

        formattedSubs = header+styles+events
        return formattedSubs
