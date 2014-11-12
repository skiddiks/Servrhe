# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.utils import getProcessOutputAndValue
from bs4 import BeautifulSoup
import collections, os, re, struct, time, shutil

dependencies = []

A_TO_AN = {
    1: 1,
    2: 2,
    3: 3,
    4: 7,
    5: 8,
    6: 9,
    7: 4,
    8: 5,
    9: 6
}

LINE = collections.namedtuple("Line", ["id", "number", "type", "style", "layer", "position", "text", "nocommenttext", "cleantext", "visibletext", "tagtext", "parentext", "start", "end", "duration", "length", "cps"])
LINE_TYPES = collections.namedtuple("Line_Types", ["COMMENT", "DIALOGUE", "OP", "ED", "SIGN", "SKIPPED"])._make(range(6))
INFO    = lambda h,m=None,bg=False: u"\u0002\u0003{}12{}{}\u000F{}".format("00," if bg else "", h, "" if m is None else ":", u"" if m is None else " "+m)
WARNING = lambda h,m=None,bg=False: u"\u0002\u0003{}08{}{}\u000F{}".format("00," if bg else "", h, "" if m is None else ":", u"" if m is None else " "+m)
ERROR   = lambda h,m=None,bg=False: u"\u0002\u0003{}05{}{}\u000F{}".format("00," if bg else "", h, "" if m is None else ":", u"" if m is None else " "+m)

def timeToInt(time):
    p = time.split(":")
    c = p.pop().split(".")
    ms = int((c.pop()+"000")[:3]) if len(c) > 1 else 0
    s = int(c.pop())
    m = int(p.pop()) if p else 0
    h = int(p.pop()) if p else 0
    return ((h * 60 + m) * 60 + s) * 1000 + ms

def intToTime(i, short = False):
    ms = i % 1000
    i /= 1000
    s = i % 60
    i /= 60
    m = i % 60
    h = i / 60
    h = str(h) if short else ("00" + str(h))[-2:]
    m = ("00" + str(m))[-2:]
    s = ("00" + str(s))[-2:]
    ms = ("00" + str(ms/10))[-2:] if short else (("000" + str(ms))[-3:] + "000000000")[:9]
    return "%s:%s:%s.%s" % (h, m, s, ms)

class Module(object):
    def __init__(self, master):
        self.master = master
        self.reviews = {}
        self.last_review = None
        self.show_scripts = {}

    def stop(self):
        pass

    def timeToInt(self, time):
        return timeToInt(time)

    def intToTime(self, i, short = False):
        return intToTime(i, short)

    def getParser(self, filename = None):
        return SubParser(filename)
    
    def getFonts(self, folder, filename):
        exception = self.master.modules["commands"].exception

        try:
            subs = SubParser(os.path.join(folder, filename))
        except:
            log.err("Problem parsing subs for {}".format(filename))
            raise exception(u"Subfile malformed")

        styles = dict([(x["Name"], x["Fontname"].lower()) for x in subs.styles.values()])
        fonts = set()
        for line, event in enumerate(subs.events):
            if event["key"] != "Dialogue":
                continue
            if event["Style"] not in styles:
                raise exception(u"Invalid style on line {:03d}: {}".format(line + 1, event["Style"]))
            fonts.add(styles[event["Style"]])
            # Warning: This will catch all instances of \fnXXX, not just ASS tags
            fonts |= set([x.lower() for x in re.findall(r"\\fn([^\\}]+)", event["Text"])])
        return fonts

    def getFontName(self, folder, filename):
        exception = self.master.modules["commands"].exception
        TAG_ID = 1
        TAG_DATA = []
        ntoffset, offset, records = None, None, None
        with open(os.path.join(folder, filename), "rb") as f:
            data = f.read()

        tables = struct.unpack_from(">H", data, 4)[0]
        for i in range(tables):
            tag = data[i*16 + 12:i*16 + 16]
            if tag == "name":
                ntoffset = struct.unpack_from(">I", data, i*16 + 20)[0]
                offset = struct.unpack_from(">H", data, ntoffset + 4)[0]
                records = struct.unpack_from(">H", data, ntoffset + 2)[0]

                if ntoffset is not None:
                    break

        if offset is None or ntoffset is None:
            raise exception(u"Couldn't parse font metadata for file: {}".format(filename))

        storage = ntoffset + offset
        for j in range(records):
            id = struct.unpack_from(">H", data, ntoffset + j*12 + 12)[0]
            length = struct.unpack_from(">H", data, ntoffset + j*12 + 14)[0]
            offset = struct.unpack_from(">H", data, ntoffset + j*12 + 16)[0]

            if id != TAG_ID:
                continue

            value = data[storage + offset:storage + offset + length]
            value2 = "".join([x for x in value if x != "\x00"])
            try:
                TAG_DATA.append(value2.decode("utf8").lower())
            except:
                try:
                    TAG_DATA.append(value.decode("utf-16-be").lower())
                except:
                    TAG_DATA.append(value2.decode("cp1252").lower())

        return TAG_DATA


    @inlineCallbacks
    def preview(self, guid, folder, premux, preview, webm, isRelease = False):
        dispatch = self.master.modules["commands"].dispatch
        exception = self.master.modules["commands"].exception
        ftp = False
        time = None

        if webm and webm > 60:
            raise exception(u"Max duration of a webm preview is 60 seconds. You asked for {:.03f} seconds.".format(webm))

        # Fuck unicode
        if premux.encode("ascii", "ignore").decode("ascii") != premux:
            shutil.copy(os.path.join(guid, premux).encode("utf8"), os.path.join(guid, "non_unicode_filename_hack.mkv"))
            premux = "non_unicode_filename_hack.mkv"

        for ext in ["webm", "jpg", "jpeg", "png", "gif"]:
            try:
                dispatch("update", guid, u"Determining last modified {} file".format(ext))
                preview_image = yield self.master.modules["ftp"].getLatest(folder, "*.{}".format(ext))
                preview_ext = ext
                dispatch("update", guid, u"Downloading".format(preview_image))
                yield self.master.modules["ftp"].get(folder, preview_image, guid)
                os.rename(os.path.join(guid, preview_image), os.path.join(guid, "preview.{}".format(ext)))
                ftp = True
                break
            except:
                continue

        if preview == "ftp" and not ftp:
            raise exception(u"Aborted releasing {}: Couldn't find preview image on FTP".format(show.name.english))

        if not ftp or (preview is not None and preview != "ftp") or (webm and preview_ext != "webm"):
            if preview is None or "+" in preview:
                try:
                    if isRelease:
                        raise Exception(u"Skipping downloading XML file")

                    dispatch("update", guid, u"Determining last modified xml file")
                    chapters = yield self.master.modules["ftp"].getLatest(folder, "*.xml")

                    dispatch("update", guid, u"Downloading {}".format(chapters))
                    yield self.master.modules["ftp"].get(folder, chapters, guid)
                    with open(os.path.join(guid, chapters), "r") as f:
                        soup = BeautifulSoup(f.read(), "xml", from_encoding="utf8")
                    out = "\n".join(["CHAPTER{0:02d}={1}\nCHAPTER{0:02d}NAME={2}".format(index + 1, e.find("ChapterTimeStart").string.encode("utf8"), e.find("ChapterString").string.encode("utf8")) for index, e in enumerate(soup("ChapterAtom"))])

                except Exception as e:
                    dispatch("update", guid, u"Extracting chapters from premux")
                    out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("mkvextract"), args=["chapters", "-s", os.path.join(guid, premux).encode("utf8")], env=os.environ)

                    if code != 0:
                        self.log(out)
                        self.log(err)
                        raise exception(u"Aborted previewing {}: Couldn't extract chapters.".format(show.name.english))

                chapters = [l.partition("=")[2].lower() for l in out.split("\n")]
                chapters = [(n, {"start": self.master.modules["subs"].timeToInt(t), "length": 0}) for n,t in zip(chapters[1::2], chapters[0::2])]
                for a, b in zip(chapters, chapters[1:]):
                    a[1]["length"] = b[1]["start"] - a[1]["start"]
                chapters = dict(chapters)

                if not chapters:
                    raise exception(u"Aborted previewing {}: No chapters to make a preview image from.".format(show.name.english))

            if preview is None:
                time = chapters["part a"]["start"] if "part a" in chapters else sorted(chapters.values(), key=lambda x: x["length"], reverse=True)[0]["start"]
                time += 30000
            elif "." not in preview:
                conversion = float(24000) / 1001
                time = int(int(preview) / conversion * 1000)
            elif "+" not in preview:
                time = self.master.modules["subs"].timeToInt(preview)
            else:
                chapter, _, offset = preview.partition("+")
                if chapter not in chapters:
                    raise exception(u"Aborted previewing {}: Requested chapter \"{}\" not found".format(show.name.english, chapter))
                time = chapters[chapter]["start"] + self.master.modules["subs"].timeToInt(offset)

            if webm and preview is None:
                rough_time = self.master.modules["subs"].intToTime(time, short=True)
                fine_time = "0.000"
            elif time > 20000:
                rough_time = self.master.modules["subs"].intToTime(time - 20000, short=True)
                fine_time = "20.000"
            else:
                rough_time = "0.000"
                fine_time = self.master.modules["subs"].intToTime(time, short=True)


            dispatch("update", guid, u"Generating preview image")

            if webm:
                preview_ext = "webm"
                args = [
                    "-y", # Overwrite files with the same name
                    "-ss", rough_time,
                    "-i", os.path.join(guid, premux).encode("utf8"),
                    "-ss", fine_time,
                    "-t", "{:0.3f}".format(webm),
                    "-an", # Disable audio
                    "-sn", # Disable subs
                    "-f", "webm", # Yes, this is webm
                    "-c:v", "libvpx", # Use standard webm video codec
                    "-b:v", "1M", # 1mbps is plenty
                    "-vf", "scale=-1:720", # 720p
                    "-quality", "best", # "best" quality
                    "-threads", "0", # Speed up encoding
                    "-cpu-used", "0", # IDFK
                    "-slices", "8", # Black magic
                    "-auto-alt-ref", "1" # ????????
                ]
                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("ffmpeg"), args=args+["-pass", "1", "/dev/null"], env=os.environ)
                if code == 0:
                    out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("ffmpeg"), args=args+["-pass", "2", os.path.join(guid, "preview.{}".format(preview_ext))], env=os.environ)
                    
            else:
                preview_ext = "jpg"
                extraargs = []
                if preview is None:
                    extraargs.extend(["-vf", "select='eq(pict_type,I)'", "-vsync", "2"])
                #extraargs.extend(["-vf", "colormatrix=bt709:bt601"])
                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("ffmpeg"), args=[
                    "-y", # Overwrite files with the same name
                    "-ss", rough_time,
                    "-i", os.path.join(guid, premux).encode("utf8"),
                    "-ss", fine_time
                ] + extraargs + [
                    "-vframes", "1",
                    os.path.join(guid, "preview.{}".format(preview_ext))
                ], env=os.environ)

            if code != 0:
                self.log(out)
                self.log(err)
                raise exception(u"Aborted previewing {}: Couldn't generate preview image.".format(show.name.english))

        try:
            with open(os.path.join(guid, "preview.{}".format(preview_ext)), "rb") as f:
                preview = {"name": (u"{}.{}".format(premux, preview_ext)).encode("utf8"), "data": f.read()}
        except IOError:
            raise exception(u"Aborted previewing {}: Couldn't open preview image.".format(show.name.english))

        dispatch("update", guid, u"Uploading {} to blog".format(preview["name"]))
        img_link = yield self.master.modules["blog"].uploadImage(**preview)

        dispatch("update", guid, u"Uploading preview image to FTP")
        yield self.master.modules["ftp"].put(guid, u"preview.{}".format(preview_ext), folder)
        yield self.master.modules["ftp"].upload(folder)

        if time is None:
            hovertext = None

        else:
            if isRelease:     
                dispatch("update", guid, u"Extracting script from release")
                out, err, code = yield getProcessOutputAndValue(self.master.modules["utils"].getPath("mkvextract"), args=["tracks", os.path.join(guid, premux).encode("utf8"), "2:{}".format(os.path.join(guid, "script.ass"))], env=os.environ)
                if code != 0:
                    self.log(u"{}", out.decode("utf8"))
                    self.log(u"{}", err.decode("utf8"))
                    script = None
                else:
                    script = "script.ass"
            else:
                try:
                    dispatch("update", guid, u"Determining last modified ass file")
                    script = yield self.master.modules["ftp"].getLatest(folder, "*.ass")
                    dispatch("update", guid, u"Downloading {}".format(script))
                    yield self.master.modules["ftp"].get(folder, script, guid)
                except:
                    script = None

            hovertext = self.master.modules["subs"].getBestLine(guid, script, time) if script is not None else None

        returnValue({"text": hovertext, "link": img_link})


    def qc(self, folder, filename):
        exception = self.master.modules["commands"].exception
        results = {
            "sorted": True,
            "total": 0,
            "comments": 0,
            "dialogue": 0,
            "OP": 0,
            "ED": 0,
            "signs": 0,
            "skipped": 0,
            "linebreaks": [],
            "italics": [],
            "honorifics": [],
            "zero duration": [],
            "sign missing blur": [],
            "oped missing blur": [],
            "malformed": [],
            "unbalanced": [],
            "malformed comments": [],
            "disjointed": [],
            "italic fail": [],
            "overlap": [],
            "gap": [],
            "default layer": [],
            "double space": [],
            "double period": [],
            "double comma": [],
            "inside quotes": [],
            "outside quotes": [],
            "jdpsetting": [],
            "brainchild": [],
            # 2014/01/06 (YYYY/MM/DD)
            "flashing": [],
            "redundant": [],
            "double word": [],
            "hard to read": [],
            "unreadable": [],
            "negative duration": [],
        }
        errors = {}

        try:
            subs = SubParser(os.path.join(folder, filename))
        except:
            log.err("Problem parsing subs for {}".format(filename))
            raise exception(u"Subfile malformed")

        if "YCbCr Matrix" not in subs.info or subs.info["YCbCr Matrix"] != "TV.709":
            raise exception(u"YCbCr Matrix MUST be set to \"TV.709\" in the ASS file header")

        if "ScaledBorderAndShadow" not in subs.info or subs.info["ScaledBorderAndShadow"] != "yes":
            raise exception(u"ScaledBorderAndShadow MUST be set to \"yes\" in the ASS file header")

        lines = []
        for index, line in enumerate(subs.events):
            number = index + 1
            text = line["Text"].decode("utf8")
            nocommenttext = re.sub(r"\{[^}]*\}?", lambda m: m.group(0) if "\\" in m.group(0) else "", text)
            cleantext = re.sub(r"\{[^}]*\}?", "", text)
            # merge disjointed tags, remove tags that aren't alpha tags, remove empty tags,
            # remove invisible text between two FF alpha tags, remove invisible text between alpha tags
            # remove the alpha tags, turn \n and \N into spaces
            visibletext =   re.sub(r"\s?(\\[nN])+\s?", " ",
                                re.sub(r"\{[^}]*\}", "",
                                    re.sub(r"\{\\alpha&HFF&\}[^{]*", "",
                                        re.sub(r"\{\\alpha&HFF&\}[^{]*(?=\{\\alpha&HFF&\})", "",
                                            re.sub(r"\{(?!\\alpha)[^}]*\}?", "",
                                                re.sub(r"\{[^}]*(\\alpha&H[0-9A-F][0-9A-F]&)[^}]*\}", r"{\1}",
                                                    re.sub(r"\{([^}]*)\}\{", r"{\1", text)))))))
            tagtext = re.sub(r"[^{]*(\{[^}]*\})[^{]*", r"\1", nocommenttext)
            # Generate parentext
            parentext = re.sub(r"[^\(\)]", "", tagtext)
            while "(())" in parentext:
                parentext = parentext.replace("(())", "()")
            parentext = parentext.replace("()", "")

            an_match = re.search(r"\\an(\d)", tagtext)
            a_match = re.search(r"\\a(\d)", tagtext)

            if "\\pos" in tagtext:
                position = 0
            elif an_match:
                position = int(an_match.group(1))
            elif a_match:
                position = A_TO_AN[int(a_match.group(1))]
            elif line["Style"] in subs.styles:
                position = int(subs.styles[line["Style"]]["Alignment"])
            else:
                position = 2

            start = line["time"]
            end = timeToInt(line["End"])
            duration = end - start
            length = len(re.sub(r"[ ,\.\"]", "", visibletext))
            cps = length / (duration / 1000.0) if duration else 0 # Convert milliseconds to seconds

            # Determine type & track number of lines of each
            if line["Effect"] == "qcd":
                results["skipped"] += 1
                line_type = LINE_TYPES.SKIPPED
            elif line["key"] == "Comment":
                results["comments"] += 1
                line_type = LINE_TYPES.COMMENT
            elif "defa" in line["Style"].lower() or "alt" in line["Style"].lower():
                results["dialogue"] += 1
                line_type = LINE_TYPES.DIALOGUE
            elif line["Style"].lower().startswith("op"):
                results["OP"] += 1
                line_type = LINE_TYPES.OP
            elif line["Style"].lower().startswith("ed"):
                results["ED"] += 1
                line_type = LINE_TYPES.ED
            else:
                results["signs"] += 1
                line_type = LINE_TYPES.SIGN
            
            results["total"] += 1

            lines.append(LINE(index, number, line_type, line["Style"], int(line["Layer"]), position, text, nocommenttext, cleantext, visibletext, tagtext, parentext, start, end, duration, length, cps))

        for line in lines:
            def addError(category, text):
                results[category].append(line.number)
                if line.number not in errors:
                    errors[line.number] = []
                errors[line.number].append(text)

            # Skip checking comments
            if line.type == LINE_TYPES.COMMENT or line.type == LINE_TYPES.SKIPPED:
                continue

            # Check for missing blur
            if line.text and line.duration and "\\blur" not in line.tagtext and "\\be" not in line.tagtext and re.match("^{[^}]*}$", line.text) is None and not line.text.startswith("{first"):
                if line.type == LINE_TYPES.OP or line.type == LINE_TYPES.ED:
                    addError("oped missing blur", WARNING("Missing Blur", line.text))
                elif line.type == LINE_TYPES.SIGN:
                    addError("sign missing blur", WARNING("Missing Blur", line.text))

            # Check for malformed tags
            highlighted, changes = re.subn("|".join([r"\\\\", r"\\}", r"}}", r"{{", r"\\blur\.", r"\\bord\.", r"\\shad\.", r"\\(alpha|[1234]a)(?!&H[0-9A-Fa-f]{2}&|$|\\)", r"\\([1234]c)(?!&H[0-9A-Fa-f]{6}&)"]), lambda m: ERROR(m.group(0), bg=True), line.text, flags=re.I)
            if changes:
                addError("malformed", ERROR("Malformed Tags", highlighted))

            # Check for redundant tags
            redundanttags = set()
            tags = ["blur","be","bord","shad","fs","fsp","fscx","fscy","frz","frx","fry","fax","fay","c","2c","3c","4c","1a","2a","3a","4a","alpha"]
            for tagchunk in re.findall(r"{[^}]*}", line.tagtext):
                if "\\t" in tagchunk:
                    continue
                for tag in tags:
                    tagregex = r"\\{}(?=[-&\d])".format(tag)
                    if len(re.findall(tagregex, tagchunk)) > 1:
                        redundanttags.add(tagregex)

            if redundanttags:
                highlighted, changes = re.subn("|".join(redundanttags), lambda m: ERROR(m.group(0), bg=True), line.text)
                if changes:
                    addError("redundant", ERROR("Redundant Tags", highlighted))

            # Check for unbalanced parentheses
            if line.parentext:
                addError("unbalanced", ERROR("Unbalanced Parentheses", line.text.replace("(", ERROR("(", bg=True)).replace(")", ERROR(")", bg=True))))
                
            # Check for disjointed tags
            highlighted, changes = re.subn(r"{\\[^}]*}{\\[^}]*}", lambda m: ERROR(m.group(0), bg=True), line.text, flags=re.I)
            if changes:
                addError("disjointed", ERROR("Disjointed Tags", highlighted))

            # Check for malformed comments
            highlighted, changes = re.subn(r"[{}]", lambda m: ERROR(m.group(0), bg=True), line.cleantext, flags=re.I)
            if changes:
                addError("malformed comments", ERROR("Malformed Comments", highlighted))

            # Check for italics fail (we can't handle "\r"esets)
            if "\\r" not in line.tagtext:
                for tag1, tag2 in re.findall(r"(?=\\i([01]?)[\\}].*?\\i([01]?)[\\}])", r"\\i" + line.text, flags=re.I):
                    i1 = int(tag1 if tag1 else subs.styles[line.style]["Italic"])
                    i2 = int(tag2 if tag2 else subs.styles[line.style]["Italic"])
                    if i1 == i2:
                        defaultitalic = "ON" if int(subs.styles[line.style]["Italic"]) else "OFF"
                        italichelp = " (You forgot the default italics for this line is {})".format(defaultitalic) if not tag1 or not tag2 else ""
                        addError("italic fail", ERROR("Italics Fail"+italichelp, re.sub(r"\\i[01]?", lambda m: ERROR(m.group(0), bg=True), line.text, flags=re.I)))
                        break

            # Check quotation punctuation
            highlighted, changes = re.subn(r"[,.]\"", lambda m: WARNING(m.group(0), bg=True), line.cleantext, flags=re.I)
            if changes:
                addError("inside quotes", WARNING("Punctuation inside quotes", highlighted))

            highlighted, changes = re.subn(r"\"[,.]", lambda m: WARNING(m.group(0), bg=True), line.cleantext, flags=re.I)
            if changes:
                addError("outside quotes", WARNING("Punctuation outside quotes", highlighted))

            # Check jdpsetting
            highlighted, changes = re.subn(r"{\\an8\\bord[\d\.]+\\pos\([\d\., ]*\)}|\bembarass\b|\ba\s+women\b|'ve\s+have", lambda m: WARNING(m.group(0), bg=True), line.text, flags=re.I)
            if changes:
                addError("jdpsetting", WARNING("jdpsetting", highlighted))

            # Check for brainchild derps ("senpai")
            highlighted, changes = re.subn(r"se[nm]pai|[wt]here're|this'[sd]|when'[drv]|guys'[rv]e|ll've", lambda m: ERROR(m.group(0), bg=True), line.visibletext, flags=re.I)
            if changes:
                addError("brainchild", ERROR("Brainchildesque Stupidity", highlighted))

            # Check for zero duration
            if line.duration == 0 and line.visibletext and line.end:
                addError("zero duration", INFO("Zero duration", line.text))

            # Check for negative duration
            if line.duration < 0:
                addError("negative duration", ERROR("Negative duration [{:d}ms]".format(line.duration), line.text))

            # Dialogue specific tests
            if line.type == LINE_TYPES.DIALOGUE:

                # Check for default layer (may cause overlap with typesetting)
                if line.layer == 0:
                    addError("default layer", WARNING("Default Layer", "Dialogue should be on a high layer (5+) to ensure it doesn't overlap with typesetting"))

                # Check for double spaces
                if "  " in line.visibletext:
                    addError("double space", WARNING("Double Space", line.visibletext.replace("  ", WARNING("  ", bg=True))))

                # Check for double periods
                highlighted, changes = re.subn(r"([^\.])(\.\.)([^\.]|$)", lambda m: m.group(1) + ERROR(m.group(2), bg=True) + m.group(3), line.visibletext, flags=re.I)
                if changes:
                    addError("double period", WARNING("Double Period", highlighted))

                # Check for double commas
                if ",," in line.visibletext:
                    addError("double comma", WARNING("Double Comma", line.visibletext.replace(",,", WARNING(",,", bg=True))))

                # Check for double words
                highlighted, changes = re.subn(r"\b([\w']+)(\s+)(?=\1\b)", lambda m: ERROR(m.group(1), bg=True) + m.group(2), line.visibletext) # Case sensitive on purpose!
                if changes:
                    addError("double word", WARNING("Double Word", highlighted))

                # Check for linebreaks
                if "\\N" in line.cleantext:
                    addError("linebreaks", INFO("Linebreak", line.cleantext.replace("\\N", INFO("\\N", bg=True))))

                # Check for italics
                if "\\i1" in line.text:
                    addError("italics", INFO("Italics", line.text.replace("\\i1", INFO("\\i1", bg=True))))

                # Check for honorifics
                highlighted, changes = re.subn(r"[a-z](-({}))\b".format("|".join(["san", "kun", "chan", "sama", "se[nm]pai", "sensei"])), lambda m: m.group(1) + WARNING(m.group(1), bg=True), line.visibletext, flags=re.I)
                if changes:
                    addError("honorifics", WARNING("Honorifics", highlighted))

                # Compare against previous line
                prevline = None
                prevlineindex = line.id - 1
                while prevlineindex >= 0 and lines[prevlineindex].type != LINE_TYPES.DIALOGUE:
                    prevlineindex -= 1
                if prevlineindex >= 0:
                    prevline = lines[prevlineindex]

                    # Ensure start times are sorted
                    if prevline.start > line.start:
                        results["sorted"] = False

                    # Ensure lines don't flash or overlap
                    if line.position and line.position == prevline.position:
                        if line.start < prevline.end and prevline.end - line.start < 500 and line.end - prevline.end != 0 and not line["Style"].lower().startswith("alt"):
                            errortext = u"Current line starts {:d}ms before previous line ends\n[{}-{} | Pos={:d}] {}\n[{}-{} | Pos={:d}] {}".format(prevline.end - line.start,
                                intToTime(prevline.start, short=True), intToTime(prevline.end, short=True), prevline.position, prevline.text,
                                intToTime(line.start, short=True), intToTime(line.end, short=True), line.position, line.text)
                            addError("overlap", ERROR("Overlapping Lines", errortext))
                        if line.start > prevline.end and line.start - prevline.end < 200:
                            errortext = u"Current line starts {:d}ms after previous line ends\n[{}-{}] {}\n[{}-{}] {}".format(line.start - prevline.end,
                                intToTime(prevline.start, short=True), intToTime(prevline.end, short=True), prevline.text,
                                intToTime(line.start, short=True), intToTime(line.end, short=True), line.text)
                            addError("gap", WARNING("Flashing Lines", errortext))

                    # Check for flashing lines
                    if 50 <= line.duration <= 500 and line.length > 8 and line.cleantext != prevline.cleantext:
                        addError("flashing", WARNING("Flashing line (under 500ms long)", "{:d}ms long".format(line.duration)))

                # Check readability
                if line.duration >= 50 and "alpha" not in line.tagtext and (not prevline or line.cleantext != prevline.cleantext):
                    if (line.cps >= 30) or (line.cps > 26 and line.length > 30):
                        addError("unreadable", WARNING("Unreadable Line [{:d} characters in {:d}ms = {:0.2f} CPS]".format(line.length, line.duration, line.cps), line.visibletext))
                    elif (line.cps > 26) or (line.cps > 23 and line.length > 25) or (line.cps == 23 and line.length > 60):
                        addError("hard to read", WARNING("Hard To Read Line [{:d} characters in {:d}ms = {:0.2f} CPS]".format(line.length, line.duration, line.cps), line.visibletext))

        self.reviews[filename] = errors
        self.last_review = filename
        return results

    def getBestLine(self, folder, filename, time):
        exception = self.master.modules["commands"].exception

        try:
            subs = SubParser(os.path.join(folder, filename))
        except:
            log.err("Problem parsing subs for {}".format(filename))
            raise exception(u"Subfile malformed")

        lines = []
        for line in subs.events:
            start, end = timeToInt(line["Start"]), timeToInt(line["End"])
            if line["key"] == "Dialogue" and start < time < end:
                lines.append(line)

        if "default" in [l["Style"].lower() for l in lines]:
            lines = filter(lambda l: l["Style"].lower() == "default", lines)

        lines.sort(key=lambda l: len(l["Text"]))

        return re.sub("{[^}]*}", "", lines[0]["Text"]).replace("\N", " ").decode("utf8") if lines else None

class SubParser(object):
    info_output = ("Title","PlayResX","PlayResY","ScaledBorderAndShadow","ScriptType","WrapStyle")
    def __init__(self, filename = None):
        self.series = self.episode = None
        self.info = {}
        self.style_fields = []
        self.styles = {}
        self.event_fields = []
        self.events = []
        self.keywords = []
        if filename:
            self.load(filename)
    def load(self, filename):
        m = re.match(r"(.+?)(\d+)(-|_)", filename)
        if m:
            self.series = m.group(1)
            self.episode = m.group(2)
        with open(filename) as f:
            INFO, STYLE, EVENT = range(3)
            state = None
            for line in f:
                line = line.strip()
                if not line:
                    continue
                elif line == "﻿[Script Info]":
                    state = INFO
                elif line == "[V4+ Styles]":
                    state = STYLE
                elif line == "[Events]":
                    state = EVENT
                elif state == INFO:
                    if line[0] == ";":
                        continue
                    key, _, value = line.partition(": ")
                    if value:
                        self.info[key] = value
                elif state == STYLE:
                    key, _, value = line.partition(": ")
                    if key == "Format":
                        self.style_fields = [v.strip() for v in value.split(",")]
                    elif key == "Style":
                        s = dict(zip(self.style_fields, [v.strip() for v in value.split(",", len(self.style_fields)-1)]))
                        self.styles[s["Name"]] = s
                elif state == EVENT:
                    key, _, value = line.partition(": ")
                    if key == "Format":
                        self.event_fields = [v.strip() for v in value.split(",")]
                    elif key == "Dialogue" or key == "Comment":
                        s = dict(zip(self.event_fields, [v.strip() for v in value.split(",", len(self.event_fields)-1)]))
                        s["time"] = timeToInt(s["Start"])
                        s["key"] = key
                        for k in ("MarginL","MarginR","MarginV"):
                            s[k] = str(int(s[k]))
                        if len(s["Text"]) > 2 and s["Text"][0] == "{" and s["Text"][-1] == "}" and "{" not in s["Text"][1:-1] and "}" not in s["Text"][1:-1]:
                            args = s["Text"][1:-1].split("|")
                            keyword = args.pop(0)
                            self.keywords.append({"line": len(self.events), "keyword": keyword, "args": args, "time": s["time"]})
                        self.events.append(s)
    def merge(self, other):
        if self.style_fields != other.style_fields:
            raise Exception("Style fields are not identical, can not merge.")
        if self.event_fields != other.event_fields:
            raise Exception("Event fields are not identical, can not merge.")
        self.merge_info(other)
        self.merge_styles(other)
        self.merge_events(other)
    def merge_info(self, other):
        self.info.update(other.info)
    def merge_styles(self, other):
        if self.style_fields != other.style_fields:
            raise Exception("Style fields are not identical, can not merge.")
        for k, v in other.styles.iteritems():
            if k in self.styles and v != self.styles[k]:
                print "'%s' style conflicts:" % k
                print "1: %s" % self.styles[k]
                print "2: %s" % v
                choice = 0
                while choice not in (1,2):
                    choice = int(raw_input("Select a style: "))
                if choice == 1:
                    continue
            self.styles[k] = v
    def merge_events(self, other):
        if self.event_fields != other.event_fields:
            raise Exception("Event fields are not identical, can not merge.")
        for keyword in other.keywords:
            keyword["line"] += len(self.events)
            self.keywords.append(keyword)
        self.events.extend(other.events)
    def sort(self):
        self.events.sort(self.time_sort)
    def time_sort(self, a, b):
        if a["time"] < b["time"]:
            return -1
        elif b["time"] < a["time"]:
            return 1
        else:
            return 0
    def __str__(self):
        self.sort()
        lines = []
        lines.append("[Script Info]")
        lines.append("Title: %s" % self.info["Title"])
        del self.info["Title"]
        info = self.info.items()
        info.sort()
        for k, v in info:
            if k in self.info_output:
                lines.append("%s: %s" % (k,v))
        lines.append("")
        lines.append("[V4+ Styles]")
        lines.append("Format: " + ", ".join(self.style_fields))
        styles = self.styles.items()
        styles.sort()
        for k, v in styles:
            l = []
            for k in self.style_fields:
                l.append(v[k])
            lines.append("Style: %s" % ",".join(l))
        lines.append("")
        lines.append("[Events]")
        lines.append("Format: " + ", ".join(self.event_fields))
        for v in self.events:
            l = []
            for k in self.event_fields:
                l.append(v[k])
            lines.append("%s: %s" % (v["key"], ",".join(l)))
        return "\n".join(lines)
    def create_style(self, style = {}, **kwargs):
        default = {
            "Name": "Default",
            "Fontname": "LTFinnegan Medium",
            "Fontsize": "50",
            "PrimaryColour": "&H00FFFFFF",
            "SecondaryColour": "&H000000FF",
            "OutlineColour": "&H00000000",
            "BackColour": "&H00000000",
            "Bold": "0",
            "Italic": "0",
            "Underline": "0",
            "StrikeOut": "0",
            "ScaleX": "100",
            "ScaleY": "100",
            "Spacing": "0",
            "Angle": "0",
            "BorderStyle": "1",
            "Outline": "2",
            "Shadow": "1",
            "Alignment": "2",
            "MarginL": "60",
            "MarginR": "60",
            "MarginV": "30",
            "Encoding": "1"
        }
        default.update(style)
        default.update(kwargs)
        self.styles[default["Name"]] = default
    def create_event(self, event = {}, **kwargs):
        default = {
            "Layer": "0",
            "Start": "0:00:00.00",
            "End": "1:00:00.00",
            "Style": "Default",
            "Name": "",
            "MarginL": "0",
            "MarginR": "0",
            "MarginV": "0",
            "Effect": "",
            "Text": "",
            "time": 0,
            "key": "Dialogue"
        }
        default.update(event)
        default.update(kwargs)
        self.events.append(default)




"""
script_name="Quality Check"
script_description="Quality Check"
script_author="unanimated"
script_version="2.1"

require "clipboard"

function qc(subs, sel)

sorted=0    mblur=0     layer=0     malf=0      inside=0    comment=0   dialog=0    bloped=0    contr=0 
dis=0       over=0      gap=0       dspace=0    dword=0     outside=0   op=0        ed=0        sign=0
italics=0   lbreak=0    hororifix=0 zeroes=0    badita=0    dotdot=0    comfail=0
zerot=0     halfsek=0   readableh=0 unreadable=0    saurosis=0  dupli=0     negadur=0
report=""   styles=""   misstyles=""    fontlist="" fontable={}

  if pressed=="Clear QC" then
    for i=1, #subs do
        if subs[i].class=="dialogue" then
            local line=subs[i]
        line.actor=line.actor
        :gsub("%s?%.%.%.timer pls","")
        :gsub("%s?%[time gap %d+ms%]","")
        :gsub("%s?%[overlap %d+ms%]","")
        :gsub("%s?%[negative duration%]","")
        :gsub("%s?%[zero time%]","")
        :gsub("%s?%[0 time%]","")
        line.effect=line.effect
        :gsub("%s?%[malformed tags%]","")
        :gsub("%s?%[disjointed tags%]","")
        :gsub("%s?%[redundant tags%]","")
        :gsub("%s?%.%.%.sort by time pls","")
        :gsub("%s?%[doublespace%]","")
        :gsub("%s?%[double word%]","")
        :gsub("%s?%[italics fail%]","")
        :gsub(" {\\Stupid","")
        :gsub("%s?%[stupid contractions%]","")
        :gsub("%s?%-MISSING BLUR%-","")
        :gsub("%s?%[%.%.%]","")
        :gsub("%s?%[hard to read%??%]","")
        :gsub("%s?%[unreadable.*%]","")
        :gsub("%s?%[UNREADABLE!+%]","")
        :gsub("%s?%[under 0%.5s%]","")
            subs[i]=line
        end
    end
  end

  if pressed==">QC" then

    -- make list of styles and fonts
    for i=1, #subs do
      if subs[i].class == "style" then
    fname=subs[i].fontname
    fnam=esc(fname)
    if not fontlist:match(fnam) then fontlist=fontlist..fname.."\n" table.insert(fontable,fname) end
    styles=styles..subs[i].name..", "
    redstyles=styles
      end
    end
    
    if res.distill=="" then distill="xxxxxxxx" else distill=res.distill end

    for x, i in ipairs(sel) do
        local line=subs[i]
        local text=subs[i].text
    local style=line.style
    local effect=line.effect
    local actor=line.actor
    if style:match("Defa") or style:match("Alt") or style:match(distill) then def=1 else def=0 end
    if style:match("^OP") or style:match("^ED") then oped=1 else oped=0 end
    
    visible=text:gsub("{\\alpha&HFF&}[^{}]-({[^}]-\\alpha&H)","%1") :gsub("{\\alpha&HFF&}[^{}]*$","")   :gsub("{[^{}]-}","")
            :gsub("\\[Nn]","*") :gsub("%s?%*+%s?"," ")  :gsub("^%s+","")    :gsub("%s+$","")
    if text:match("{\\alpha&HFF&}") then alfatime=1 else alfatime=0 end
    nocomment=text:gsub("{[^\\}]-}","")
    cleantxt=text:gsub("{[^}]-}","")
    onlytags=nocomment:gsub("}[^{]-{","}{") :gsub("}[^{]+$","}")    :gsub("^[^{]+$","")
    parenth=onlytags:gsub("[^%(%)]","")     :gsub("%(%(%)%)","")    :gsub("%(%)","")
    start=line.start_time
    endt=line.end_time
    if i<#subs then nextline=subs[i+1] end
    prevline=subs[i-1]
    if prevline.class=="dialogue" then prevcleantxt=prevline.text:gsub("{[^}]-}","") else prevcleantxt="" end
    prevstart=prevline.start_time
    prevend=prevline.end_time
    dura=endt-start
    dur=dura/1000
    char=visible:gsub(" ","")   :gsub("[%.,\"]","")
    linelen=char:len()
    cps=math.ceil(linelen/dur)

    -- check if sorted by time
    if res["sorted"] then
    if prevline.class=="dialogue" and start<prevstart then
        effect=effect.." ...sort by time pls" sorted=1
    end end

      if not line.comment and line.effect~="qcd" then
    -- check for blur
    if res["blur"] and def==0 and text~=""
    and text:match("\\blur")==nil and text:match("\\be")==nil and endt>0 and text:match("^{[^}]*}$")==nil and text:match("^{first")==nil then
        if res["blurfix"] then
        text=text:gsub("^","{\\blur"..res["addblur"].."}")  text=text:gsub("({\\blur[%d%.]*)}{\\","%1\\")
        else
        effect=effect.." -MISSING BLUR-"
        mblur=mblur+1
        if oped==1 then bloped=bloped+1 end
        end
    end

    -- check for malformed tags
    if res["malformed"] then
    if text:match("{[^}]-\\\\[^}]-}")
    or text:match("\\}")  
    or text:match("\\blur%.") 
    or text:match("\\bord%.") 
    or text:match("\\shad%.")
    or text:match("\\alpha[^&\\}]")
    or text:match("\\alpha&[^H]")
    or text:match("\\alpha&H%x[^%x]")
    or text:match("\\alpha&H%x%x[^&]")
    or text:match("\\[1234]a[^&\\}]")
    or text:match("\\[1234]a&[^H]")
    or text:match("\\[1234]c[^&\\}]")
    or text:match("\\[1234]?c&[^H]")
    or text:match("\\[1234]?c&%x%x%x%x%x%x[^&]")
    or text:match("{\\[^}]*&&[^}]*}")
    or parenth~=""
    then effect=effect.." [malformed tags]" malf=malf+1 end
    clrfail=0
    for clr in text:gmatch("c&H(%x+)&") do
    if clr:len()~=6 then clrfail=1 end  end
    if clrfail==1 then effect=effect.." [malformed tags]" malf=malf+1 end
    end

    -- check for disjointed tags
    if res["disjointed"] then
    if text:match("{\\[^}]*}{\\[^}]*}")
    then effect=effect.." [disjointed tags]" dis=dis+1 end
    end

    -- check for overlaps and gaps
    if res["overlap"] then
    if prevline.class=="dialogue" and style:match("Defa") and prevline.style:match("Defa") 
    and text:match("\\an8")==nil and prevline.text:match("\\an8")==nil then
        if start<prevend and prevend-start<500 and endt-prevend~=0 then 
        actor=actor.." [overlap "..prevend-start.."ms]" over=over+1 
            if prevend-start<100 then actor=actor.." ...timer pls" end
        end
        if start>prevend and start-prevend<200 then 
        actor=actor.." [time gap "..start-prevend.."ms]" gap=gap+1 
            if start-prevend<100 then actor=actor.." ...timer pls" end
        end
        if endt==start and endt>0 and visible~="" then actor=actor.." [zero time]" zerot=zerot+1 end
        if endt<start then actor=actor.." [negative duration]" negadur=negadur+1 end
    end end

    -- check dialogue layer
    if res["dlayer"] then
    if def==1 and line.layer==0 then layer=layer+1 
    end end

    -- check for double spaces in dialogue
    if res["doublespace"] and def==1 then
        if visible:match("%s%s") then effect=effect.." [doublespace]" dspace=dspace+1 end
    end

    -- check for double words
    if res["doubleword"] and def==1 then
    visible2w=visible.."."
        for derp in visible2w:gmatch("%s?([%w%s\']+)[%p]") do
        derp2=derp:gsub("^[%a\']+","")
        for a,b in derp:gmatch("([%a\']+)%s([%a\']+)") do
        if a==b and not a:match("^%u") then effect=effect.." [double word]" dword=dword+1 end
        end
        for a,b in derp2:gmatch("([%a\']+)%s([%a\']+)") do
        if a==b and not a:match("^%u") then effect=effect.." [double word]" dword=dword+1 end
        end
        end
    end

    -- check for fucked up comments
    if visible:match("[{}]") or text:match("}[^{]-}") or text:match("{[^}]-{") then comfail=comfail+1 effect=effect.." {\\Stupid" end

    -- check for bad italics - {\i1}   {\i1}
    if res.failita and not text:match("\\r") then
      itafail=0
      itl=""
      for it in text:gmatch("\\i([01]?)[\\}]") do 
        if it=="" then styleref=stylechk(subs,line.style)
          if styleref.italics then it="1" else it="0" end
        end
      itl=itl..it end
      if itl:match("11") or itl:match("00") then itafail=1 end
      if itafail==1 then effect=effect.." [italics fail]" badita=badita+1 end
    end

    -- check readability    (some sentences are much harder to read than others, so don't take this too seriously, but over 25 is probably bad.)
    ll=linelen ra=0
    if res.read and def==1 and dura>50 and alfatime==0 and prevcleantxt~=cleantxt then      -- these could use rephrasing if possible
      if cps==23 and ll>60 then effect=effect.." [hard to read?]" ra=1 end
      if cps>23 and cps<=26 then 
        if ll>25 and ll<100 then effect=effect.." [hard to read?]" ra=1 end
        if ll>=100 then effect=effect.." [hard to read]" ra=1 end
      end
      if cps>26 and cps<30 and ll<=30 then effect=effect.." [hard to read?]" ra=1 end
    end
    
    if res.noread and def==1 and dura>50 and alfatime==0 and prevcleantxt~=cleantxt then    -- from here on, it's bad. rephrase/retime
      if cps>26 and cps<30 then
        if ll>30 and ll<=60 then effect=effect.." [unreadable]" ra=2 end
        if ll>60 then effect=effect.." [unreadable!]" ra=2 end
      end
      if cps>=30 and cps<=35 then 
        if ll<=30 then effect=effect.." [unreadable]" ra=2 end
        if ll>30 and ll<=60 then effect=effect.." [unreadable!]" ra=2 end
        if ll>60 then effect=effect.." [unreadable!!]" ra=2 end
      end
      if cps>35 then effect=effect.." [UNREADABLE!!]" ra=2 end          -- timer and editor need to be punched
    end
    if ra==1 then readableh=readableh+1 end
    if ra==2 then unreadable=unreadable+1 end

    -- check for double periods
    if def==1 then
    if visible:match("[^%.]%.%.[^%.]") or visible:match("[^%.]%.%.$") then effect=effect.." [..]" dotdot=dotdot+1 end
    end

    -- check for periods/commas inside/outside quotation marks
    if not line.comment and visible:match("[%.%,]\"") then inside=inside+1 end
    if not line.comment and visible:match("\"[%.%,][^%.]") then outside=outside+1 end

    -- check for redundant tags
    if res.redundant then dup=0
    tags1={"blur","be","bord","shad","fs","fsp","fscx","fscy","frz","frx","fry","fax","fay","c","2c","3c","4c","1a","2a","3a","4a","alpha"}
      for tax in text:gmatch("({\\[^}]-})") do
        for i=1,#tags1 do
          tag=tags1[i]
          if not tax:match("\\t") and tax:match("\\"..tag.."[%d%-&][^}]-\\"..tag.."[%d%-&]") then dup=1 end
        end
      end
    if text:match("{\\[^}]-}$") then dup=1 end
    if dup==1 then dupli=dupli+1 effect=effect.." [redundant tags]" end
    end

    -- lines under 0.5s
    if res.halfsec and def==1 and visible~="" and ll>8 and prevcleantxt~=cleantxt then
    if dura<500 and dura>50 then halfsek=halfsek+1 effect=effect.." [under 0.5s]" end
    end

    -- Hdr request against jdpsetting
    if text:match("{\\an8\\bord[%d%.]+\\pos%([%d%.%,]*%)}") then actor=" What are you doing..." end
    
    if text:match("embarass") then effect=effect.." how embarrassing" end
    
    if text:match(" a women ") then effect=effect.." a what?" end
    
    if text:match("\'ve have") then effect=effect.." Now you've have done it!" end
    
    -- retarded / pointless contractions that sound the same as not contracted / are unpronounceable
    if visible:match("[wt]here're") or visible:match("this'[sd]")  or visible:match("when'[drv]")
    or visible:match("guys'[rv]e") or visible:match("ll've")
    then contr=contr+1 effect=effect.." [stupid contractions]" end
    
    -- count OP lines
    if style:match("^OP") then op=op+1 end
    
    -- count ED lines
    if style:match("^ED") then ed=ed+1 end
    
    -- count what's probably signs
    if def==0 and oped==0 then sign=sign+1 end 
    
    -- count linebreaks in dialogue
    if res["lbreax"] and def==1 and nocomment:match("\\N") then lbreak=lbreak+1 end
    
    -- count lines with italics
    if res["italix"] and def==1 and text:match("\\i1") then italics=italics+1 end
    
    -- count honorifics
    if res["honorifix"] and def==1 then
        if visible:match("%a%-san[^%a]") or visible:match("%a%-kun[^%a]") or visible:match("%a%-chan[^%a]")
        or visible:match("%a%-sama[^%a]") or visible:match("%a%-se[mn]pai") or visible:match("%a%-dono")
        or visible:match("%a%-sensei") then hororifix=hororifix+1 end
    end
    
    -- count lines with 0 time
    if res["zero"] then
    if endt==start then zeroes=zeroes+1 actor=actor.." [0 time]" end
    end
    
    -- check for missing styles
    sty=esc(style)
    if res.mistyle and not styles:match(sty) and not misstyles:match(sty) then misstyles=misstyles..style..", " end
    
    -- list unused styles
    if res.uselesstyle then --aegisub.log("\nsty "..sty)
        if redstyles:match("^"..sty..",") or redstyles:match(", "..sty..",") then 
        redstyles=redstyles:gsub("^"..sty..", ","") redstyles=redstyles:gsub(", "..sty..", ",", ") end
    end
    
    -- collect font names
    if res.fontcheck and text:match("\\fn") then 
        for fontname in text:gmatch("\\fn([^}\\]+)") do
        fname=esc(fontname)
        if not fontlist:match(fname) then fontlist=fontlist..fontname.."\n" table.insert(fontable,fontname) end
        end
    end

    -- count dialogue lines
    if def==1 then dialog=dialog+1 end
      end
    
    -- count commented lines
    if line.comment==true then comment=comment+1 end
    
    if res.sauro and line.effect~=effect or res.sauro and line.actor~=actor then saurosis=saurosis+1 end
    line.actor=actor
    line.effect=effect
    line.text=text
        subs[i]=line
    aegisub.progress.title(string.format("Checking line: %d/%d",x,#sel))
    end
    heather(subs)
    if stitle~=nil then report=report.."Script Title: "..stitle.."\n" end
    if video~=nil then report=report.."Video File: "..video.."\n" end
    if colorspace~=nil then report=report.."Colorspace: "..colorspace.."\n" end
    if resx~=nil then report=report.."Script Resolution: "..resx.."x"..resy.."\n\n" end
    exportfonts="" table.sort(fontable)
    for f=1,#fontable do
    exportfonts=exportfonts..fontable[f]..", "
    end
    exportfonts=exportfonts:gsub(", $","")
    redstyles=redstyles:gsub(", $","")
    
    if #sel==1 then  report=report.."Selection: "..#sel.." line,   "
    else report=report.."Selection: "..#sel.." lines,   " end
    report=report.."Commented: "..comment.."\n"
    report=report.."Dialogue: "..dialog..",   OP: "..op..",   ED: "..ed..",   TS: "..sign.."\n"
    if res["lbreax"] then report=report.."Dialogue lines with linebreaks... "..lbreak.."\n" end
    if res["italix"] then report=report.."Dialogue lines with italics tag... "..italics.."\n" end
    if res["honorifix"] then report=report.."Honorifics found... "..hororifix.."\n" end
    if res["zero"] then report=report.."Lines with zero time... "..zeroes.."\n" end
    if res["uselesstyle"] and redstyles~="" then report=report.."\nRedundant (unused) styles: "..redstyles.."\n" end
    if res["fontcheck"] then report=report.."\nUsed fonts ("..#fontable.."): "..exportfonts.."\n" end
    report=report.."\n\n--------  PROBLEMS FOUND --------\n\n"
    if sorted==1 then report=report.."NOT SORTED BY TIME.\n" end
    if colorspace=="TV.601" then report=report.."COLORSPACE IS TV.601. Use TV.709 or Daiz will haunt you!\n" end
    if misstyles~="" then misstyles=misstyles:gsub(", $","") report=report.."MISSING STYLES: "..misstyles.."\n" end
    if mblur~=0 then report=report.."Non-dialogue lines with missing blur... "..mblur.."\n" end
    if bloped~=0 then report=report.."Out of those OP/ED... "..bloped.."\n" end
    if malf~=0 then report=report.."Lines with malformed tags... "..malf.."\n" end
    if dis~=0 then report=report.."Lines with disjointed tags... "..dis.."\n" end
    if dupli~=0 then report=report.."Lines with redundant tags... "..dupli.."\n" end
    if over~=0 then report=report.."Suspicious timing overlaps... "..over.."\n" end
    if gap>9 then gapu="  --  Timer a shit" else gapu="" end
    if gap~=0 then report=report.."Suspicious gaps in timing (under 200ms)... "..gap..gapu.."\n" end
    if zerot~=0 then report=report.."Lines with text but zero time... "..zerot.."\n" end
    if negadur~=0 then report=report.."Lines with negative duration... "..negadur.."\n" end
    if dspace~=0 then report=report.."Dialogue lines with double spaces... "..dspace.."\n" end
    if dword~=0 then report=report.."Dialogue lines with a double word... "..dword.."\n" end
    if dotdot~=0 then report=report.."Dialogue lines with double periods... "..dotdot.."\n" end
    if halfsek~=0 then report=report.."Dialogue lines under 0.5s... "..halfsek.."\n" end
    if readableh~=0 then report=report.."Lines that may be hard to read... "..readableh.."\n" end
    if unreadable>9 then unrdbl="  --  Editor a shit" else unrdbl="" end
    if unreadable~=0 then report=report.."Lines that may be impossible to read and should be edited or retimed... "..unreadable..unrdbl.."\n" end
    if badita~=0 then report=report.."Lines with bad italics... "..badita.."\n" end
    if contr~=0 then report=report.."Stupid / pointless contractions... "..contr.."\n" end
    if comfail~=0 then report=report.."Fucked up braces... "..comfail.."\n" end
    if inside~=0 and outside~=0 then 
    report=report.."Comma/period inside quotation marks... "..inside.."\n"
    report=report.."Comma/period outside quotation marks... "..outside.."\n" end
    if saurosis>0 and saurosis<100 then report=report.."Total lines with faggosaurosis... "..saurosis.."\n" end
    if saurosis>99 and saurosis<500 then report=report.."Total lines with faggosaurosis... "..saurosis.." -- You're doing it wrong!\n" end
    if saurosis>499 then report=report.."Total lines with faggosaurosis... "..saurosis.." -- WARNING: YOUR FAGGOSAUROSIS LEVELS ARE TOO HIGH!\n" end
    if layer~=0 and #sel>dialog then report=report.."Dialogue may overlap with TS. Set to higher layer to avoid.\n" end
    if sorted==0 and mblur==0 and malf==0 and dis==0 and over==0 and gap==0 and dspace==0 and dotdot==0 and badita==0 and comfail==0 and unreadable==0 and misstyles=="" and colorspace~="TV.601" then
    report=report.."\nCongratulations. No serious problems found." else
    if saurosis<500 then report=report.."\nPlease fix the problems and try again." end
    if saurosis>499 then report=report.."\nWHAT ARE YOU DOING?! FIX THAT SHIT, AND DON'T FUCK IT UP AGAIN NEXT TIME!" end
    end
    brcount=0
    for brk in report:gmatch("\n") do brcount=brcount+1 end
    
        reportdialog=
    {{x=0,y=0,width=45,height=1,class="label",label="Text to export:"},
    {x=0,y=1,width=45,height=brcount/2+6,class="textbox",name="copytext",value=report},}
    pressd,rez=aegisub.dialog.display(reportdialog,{"OK","Copy to clipboard","Cancel"},{ok='OK',close='Cancel'})
    if pressd=="Copy to clipboard" then clipboard.set(report) end   if pressd=="Cancel" then aegisub.cancel() end
  end
end

function dial5(subs)
    for i=1, #subs do
      if subs[i].class=="dialogue" then
    local line=subs[i]
    if line.style:match("Defa") or line.style:match("Alt") or line.style:match("Main") then
      if line.layer<5 then line.layer=line.layer+5 end
    end
    subs[i]=line
      end
    end
end

function stylechk(subs,stylename)
    for i=1, #subs do
        if subs[i].class=="style" then
        local style=subs[i]
        if stylename==style.name then
        styleref=style
        end
    end
    end
    return styleref
end

function heather(subs)
    stitle,video,colorspace,resx,resy=nil
    for i=1, #subs do
        if subs[i].class=="info" then
        local k=subs[i].key
        local v=subs[i].value
        if k=="Title" then stitle=v end
        if k=="Video File" then video=v end
        if k=="YCbCr Matrix" then colorspace=v end
        if k=="PlayResX" then resx=v end
        if k=="PlayResY" then resy=v end
    end
    end
end

function esc(str)
str=str
:gsub("%%","%%%%")
:gsub("%(","%%%(")
:gsub("%)","%%%)")
:gsub("%[","%%%[")
:gsub("%]","%%%]")
:gsub("%.","%%%.")
:gsub("%*","%%%*")
:gsub("%-","%%%-")
:gsub("%+","%%%+")
:gsub("%?","%%%?")
return str
end

function konfig(subs, sel)
    dialog_config=
    {
    {x=1,y=0,width=1,height=1,class="label",label="Note: Dialogue styles must match 'Defa' or 'Alt' or: "},
    {x=2,y=0,width=1,height=1,class="edit",name="distill",},
    {x=1,y=1,width=1,height=1,class="label",label="Analysis [applies to SELECTED lines]:"   },
        {x=1,y=2,width=1,height=1,class="checkbox",name="sorted",label="Check if sorted by time",value=true},
    {x=1,y=3,width=1,height=1,class="checkbox",name="blur",label="Check for missing blur in signs",value=true},
    {x=1,y=4,width=1,height=1,class="checkbox",name="overlap",label="Check for overlaps / gaps / zero-time lines",value=true},
    {x=1,y=5,width=1,height=1,class="checkbox",name="malformed",label="Check for malformed tags - \\blur.5, \\alphaFF, \\\\",value=true},
    {x=1,y=6,width=1,height=1,class="checkbox",name="disjointed",label="Check for disjointed tags - {\\tags...}{\\tags...}",value=true},
    {x=1,y=7,width=1,height=1,class="checkbox",name="doublespace",label="Check for double spaces in dialogue",value=true},
    {x=1,y=8,width=1,height=1,class="checkbox",name="doubleword",label="Check for double words in dialogue",value=true},
    {x=1,y=9,width=1,height=1,class="checkbox",name="read",label="Check for hard-to-read lines",value=true},
    {x=1,y=10,width=1,height=1,class="checkbox",name="noread",label="Check for unreadable lines",value=true},
    {x=1,y=11,width=1,height=1,class="checkbox",name="redundant",label="Check for redundant tags",value=true},
    {x=1,y=12,width=1,height=1,class="checkbox",name="failita",label="Check for bad italics",value=true},
    {x=1,y=13,width=1,height=1,class="checkbox",name="mistyle",label="Check for missing styles",value=true},
    {x=1,y=14,width=1,height=1,class="checkbox",name="dlayer",label="Check dialogue layer",value=true},
    {x=1,y=15,width=2,height=1,class="checkbox",name="halfsec",label="Check for dialogue lines under 0.5s",value=true,hint="bur over 1 frame and over 8 characters"},
    
    {x=2,y=1,width=2,height=1,class="label",label="More useless statistics..."},
    {x=2,y=2,width=2,height=1,class="checkbox",name="italix",label="Count dialogue lines with italics tag",value=false},
    {x=2,y=3,width=2,height=1,class="checkbox",name="lbreax",label="Count dialogue lines with linebreaks",value=false},
    {x=2,y=4,width=2,height=1,class="checkbox",name="honorifix",label="Count honorifics (-san, -kun, -chan)",value=false},
    {x=2,y=5,width=2,height=1,class="checkbox",name="zero",label="Count lines with 0 time",value=false},
    {x=2,y=6,width=2,height=1,class="checkbox",name="fontcheck",label="List used fonts",value=false},
    {x=2,y=7,width=2,height=1,class="checkbox",name="uselesstyle",label="List unused styles",value=false},
    {x=2,y=8,width=2,height=1,class="checkbox",name="sauro",label="Count lines with faggosaurosis",value=true},
    
    {x=1,y=16,width=2,height=1,class="label",label=""},
    {x=1,y=17,width=3,height=1,class="label",label="This is to help you spot mistakes. If you're using this INSTEAD of QC, you're dumb."},
    
    }   
    pressed,res=aegisub.dialog.display(dialog_config,{">QC","Clear QC","Dial 5","Fuck this fansubbing business."},
    {ok='>QC',cancel='Fuck this fansubbing business.'})  
    
    if pressed==">QC" or pressed=="Clear QC" then qc(subs, sel) end
    if pressed=="Dial 5" then dial5(subs) end
    if pressed=="Fuck this fansubbing business." then aegisub.cancel() end
end

function kyuusii(subs, sel)
    konfig(subs, sel) 
    aegisub.set_undo_point(script_name)
    return sel
end

aegisub.register_macro(script_name, script_description, kyuusii)
"""
