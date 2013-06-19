# -*- coding: utf-8 -*-

import collections, os, re, struct, time

dependencies = []

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

        styles = dict([(x["Name"], x["Fontname"]) for x in subs.styles.values()])
        fonts = set()
        for line, event in enumerate(subs.events):
            if event["key"] != "Dialogue":
                continue
            if event["Style"] not in styles:
                raise exception(u"Invalid style on line {:03d}: {}".format(line + 1, event["Style"]))
            fonts.add(styles[event["Style"]])
            # Warning: This will catch all instances of \fnXXX, not just ASS tags
            fonts |= set(re.findall(r"\\fn([^\\}]+)", event["Text"]))
        return fonts

    def getFontName(self, folder, filename):
        tags = {}
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
                break

        if ntoffset is None:
            return tags

        storage = ntoffset + offset
        for i in range(records):
            id = struct.unpack_from(">H", data, ntoffset + i*12 + 12)[0]
            length = struct.unpack_from(">H", data, ntoffset + i*12 + 14)[0]
            offset = struct.unpack_from(">H", data, ntoffset + i*12 + 16)[0]

            value = data[storage + offset:storage + offset + length]
            value = "".join([x for x in value if x != "\x00"])
            tags[id] = value

        return tags[1].decode("utf8") if 1 in tags else None

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
            "linebreaks": [],
            "italics": [],
            "honorifics": [],
            "zero length": [],
            "sign missing blur": [],
            "oped missing blur": [],
            "malformed": [],
            "disjointed": [],
            "overlap": [],
            "gap": [],
            "default layer": [],
            "double space": [],
            "inside quotes": [],
            "outside quotes": [],
            "jdpsetting": []
        }

        try:
            subs = SubParser(os.path.join(folder, filename))
        except:
            log.err("Problem parsing subs for {}".format(filename))
            raise exception(u"Subfile malformed")

        types = collections.namedtuple("Line_Types", ["COMMENT", "DIALOGUE", "OP", "ED", "SIGN"])._make(range(5))
        for index, line in enumerate(subs.events):
            number = index + 1
            text = line["Text"]
            length = timeToInt(line["End"]) - line["time"]

            # Determine type & track number of lines of each
            if line["key"] == "Comment":
                results["comments"] += 1
                line_type = types.COMMENT
            elif "defa" in line["Style"].lower() or "alt" in line["Style"].lower():
                results["dialogue"] += 1
                line_type = types.DIALOGUE
            elif line["Style"].lower().startswith("op"):
                results["OP"] += 1
                line_type = types.OP
            elif line["Style"].lower().startswith("ed"):
                results["ED"] += 1
                line_type = types.ED
            else:
                results["signs"] += 1
                line_type = types.SIGN
            
            results["total"] += 1

            # Check for missing blur
            if text and length and r"\blur" not in text and re.match("^{[^}]*}$", text) is None and not text.startswith("{first"):
                if line_type == types.OP or line_type == types.ED:
                    results["oped missing blur"].append(number)
                elif line_type == types.SIGN:
                    results["sign missing blur"].append(number)

            # Dialogue specific tests
            if line_type == types.DIALOGUE:

                # Check for default layer (may cause overlap with typesetting)
                if int(line["Layer"]) == 0:
                    results["default layer"].append(number)

                # Check for double spaces
                if "  " in text:
                    results["double space"].append(number)

                # Check for linebreaks
                if r"\N" in text:
                    results["linebreaks"].append(number)

                if r"\i1" in text:
                    results["italics"].append(number)

                for honorific in ["san", "kun", "chan", "sama"]:
                    if re.search("[a-zA-Z]-" + honorific, text):
                        results["honorifics"].append(number)
                        break

            # Non-comment tests
            if line_type != types.COMMENT:

                # Check for zero length
                if length == 0:
                    results["zero length"].append(number)

                # Check for malformed tags
                for test in [r"\\\\", r"\\}", r"}}", r"{{", r"\\blur\.", r"\\bord\.", r"\\shad\.", r"\\(alpha|[1234]a)(?!&H[0-9A-Fa-f]{2}&)"]:
                    if re.search(test, text) is not None:
                        results["malformed"].append(number)
                        break

                # Check for disjointed tags
                if re.search(r"{\\[^}]*}{\\[^}]*}", text) is not None:
                    results["disjointed"].append(number)

                # Compare against previous line
                if index > 0 and subs.events[index - 1]["key"] == "Dialogue":
                    prevline = subs.events[index - 1]

                    # Ensure start times are sorted
                    if prevline["time"] > line["time"]:
                        results["sorted"] = False

                    # Ensure lines don't flash or overlap
                    if "defa" in line["Style"].lower() and "defa" in prevline["Style"].lower() and r"\an8" not in line["Text"] and r"\an8" not in prevline["Text"]:
                        end = timeToInt(line["End"])
                        prevend = timeToInt(prevline["End"])
                        if line["time"] < prevend and prevend - line["time"] < 500 and end - prevend != 0:
                            results["overlap"].append(number)
                        if line["time"] > prevend and line["time"] - prevend < 200:
                            results["gap"].append(number)

                # Check quotation punctuation
                if re.search(r"[,.!?]\"", text) is not None:
                    results["inside quotes"].append(number)
                if re.search(r"\"[,.!?]", text) is not None:
                    results["outside quotes"].append(number)

                # Check jdpsetting
                if re.search(r"{\\an8\\bord[\d.]+\\pos\([\d., ]*\)}", text) is not None:
                    results["jdpsetting"].append(number)

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

        return re.sub("{[^}]*}", "", lines[0]["Text"]) if lines else None

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

