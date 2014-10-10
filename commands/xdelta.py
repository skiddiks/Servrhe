from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import binascii, fnmatch, os, re, shutil, zipfile, gzip

config = {
    "access": "admin",
    "help": ".xdelta [show name] (--previous) (--no-chapters) (--roman) (--crc=HEX) (--group=BSS-Commie) (--title=TITLE) || Creates an xdelta for the current episode of the show. Requires an .mkv, .ass and .xml file. Options are self explanatory."
}

def unpackScript(exception, folder, filename):
    base, _, ext = filename.rpartition(".")

    if ext == "ass":
        shutil.copy(os.path.join(folder, filename), os.path.join(folder, base))
        return unpackScript(exception, folder, base)

    elif ext == "zip":
        with zipfile.ZipFile(os.path.join(folder, filename), "r", allowZip64=True) as zf:
            scripts = fnmatch.filter(zf.namelist(), "*.ass")

            if not scripts:
                raise exception(u"Couldn't find any scripts in zip archive: {}".format(filename))
            if len(scripts) > 1:
                raise exception(u"Found too many scripts in zip archive {}: {}".format(filename, u", ".join(scripts)))

            script = scripts[0]
            zf.extract(script, folder)
        return unpackScript(exception, folder, script)

    elif ext == "gzip":
        with gzip.open(os.path.join(folder, filename), "r") as gf:
            with open(os.path.join(folder, base), "w") as f:
                f.write(gf.read())
        return unpackScript(exception, folder, base)

    else:
        return filename

def command(guid, manager, irc, channel, user, show, previous = False, no_chapters = False, no_fonts = False, no_qc = False, roman = False, crc = None, group = None, title = None, admin_mode = False):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset
    fname = "test.mkv"
    group = group if group else u"Commie"
    title = title if title else show.name.english

    if crc is not None and re.match("[0-9a-fA-F]{8}", crc) is None:
        raise manager.exception(u"Invalid CRC")

    # Step 1: Search FTP for premux + script
    folder = "{}/{:02d}".format(show.folder.ftp, episode)
    manager.dispatch("update", guid, u"Caching {}".format(folder))
    yield manager.master.modules["ftp"].download(folder)
    manager.dispatch("update", guid, u"Determining last modified xdelta file")
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")
    manager.dispatch("update", guid, u"Determining last modified ass file")
    script = yield manager.master.modules["ftp"].getLatest(folder, "*.ass")
    if not no_chapters:
        manager.dispatch("update", guid, u"Determining last modified xml file")
        chapters = yield manager.master.modules["ftp"].getLatest(folder, "*.xml")

    # Step 2: Download that shit
    manager.dispatch("update", guid, u"Downloading {}".format(premux))
    yield manager.master.modules["ftp"].get(folder, premux, guid)
    manager.dispatch("update", guid, u"Downloading {}".format(script))
    yield manager.master.modules["ftp"].get(folder, script, guid)
    if not no_chapters:
        manager.dispatch("update", guid, u"Downloading {}".format(chapters))
        yield manager.master.modules["ftp"].get(folder, chapters, guid)
        irc.msg(channel, u"Found premux, script and chapters: {}, {} and {}".format(premux, script, chapters))
    else:
        irc.msg(channel, u"Found premux and script: {} and {}".format(premux, script))

    # Step 2b: Unpack the script
    script = unpackScript(manager.exception, guid, script)

    # Step 3: Download fonts
    manager.dispatch("update", guid, u"Downloading fonts")
    fonts = yield manager.master.modules["ftp"].getFonts(folder, guid)
    irc.notice(user, u"Fonts downloaded")

    # Step 4: Verify fonts
    if not no_fonts or not admin_mode:
        needed_fonts = manager.master.modules["subs"].getFonts(guid, script)
        available_fonts = set()
        for font in fonts:
            names = manager.master.modules["subs"].getFontName(guid, font)
            if names:
                available_fonts = available_fonts.union(names)
        remaining_fonts = needed_fonts - available_fonts
        if remaining_fonts:
            required = ", ".join(list(remaining_fonts))
            required = required.decode("utf8")
            got = u", ".join(list(available_fonts))
            raise manager.exception(u"Aborted creating xdelta for {}: Missing fonts: {}. (Got: {})".format(show.name.english, required, got))

    # Step 5: QC
    if not no_qc or not admin_mode:
        listify = lambda l: ", ".join([str(n) for n in l[:20]] + ["..."] if len(l) > 20 else [str(n) for n in l])
        results = manager.master.modules["subs"].qc(guid, script)

        if show.id not in manager.master.modules["subs"].show_scripts:
            manager.master.modules["subs"].show_scripts[show.id] = []
        manager.master.modules["subs"].show_scripts[show.id].append(script)

        # Colors: INFO = 12 (blue), WARNING = 8 (orange), ERROR = 5 (red)
        irc.msg(channel, u"\u0002\u000312INFO:\u000F Total Lines: {:,d}, Comments: {:,d}, Dialogue: {:,d}, Signs: {:,d}, OP: {:,d}, ED: {:,d}, \u0002Skipped: {:,d}".format(results["total"], results["comments"], results["dialogue"], results["signs"], results["OP"], results["ED"], results["skipped"]))
        irc.msg(channel, u"\u0002\u000312INFO:\u000F Linebreaks in dialogue: {:,d}, Italics in dialogue: {:,d}, Zero duration lines: {:,d}".format(len(results["linebreaks"]), len(results["italics"]), len(results["zero duration"])))
        if results["honorifics"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} lines with honorifics: {}".format(len(results["honorifics"]), listify(results["honorifics"])))
        if results["inside quotes"] and results["outside quotes"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} lines have punctuation inside quotes: {}".format(len(results["inside quotes"]), listify(results["inside quotes"])))
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} lines have punctuation outside quotes: {}".format(len(results["outside quotes"]), listify(results["outside quotes"])))
        if results["oped missing blur"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} OP/ED lines missing blur: {}".format(len(results["oped missing blur"]), listify(results["oped missing blur"])))
        if results["sign missing blur"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} signs missing blur: {}".format(len(results["sign missing blur"]), listify(results["sign missing blur"])))
        if results["default layer"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialogue lines on default layer: {}".format(len(results["default layer"]), listify(results["default layer"])))
        if results["double space"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialogue lines containing double spaces: {}".format(len(results["double space"]), listify(results["double space"])))
        if results["double period"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialogue lines containing double periods: {}".format(len(results["double period"]), listify(results["double period"])))
        if results["double comma"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialogue lines containing double comma: {}".format(len(results["double comma"]), listify(results["double comma"])))
        if results["double word"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialogue lines containing double words: {}".format(len(results["double word"]), listify(results["double word"])))
        if results["malformed"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} malformed tags: {}".format(len(results["malformed"]), listify(results["malformed"])))
        if results["disjointed"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} disjointed tags: {}".format(len(results["disjointed"]), listify(results["disjointed"])))
        if results["redundant"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} redundant tags: {}".format(len(results["redundant"]), listify(results["redundant"])))
        if results["unbalanced"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} unbalanced parentheses: {}".format(len(results["unbalanced"]), listify(results["unbalanced"])))
        if results["malformed comments"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} malformed comments: {}".format(len(results["malformed comments"]), listify(results["malformed comments"])))
        if results["italic fail"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} italic fails: {}".format(len(results["italic fail"]), listify(results["italic fail"])))
        if results["overlap"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} overlapping lines: {}".format(len(results["overlap"]), listify(results["overlap"])))
        if results["gap"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} gaping lines: {}".format(len(results["gap"]), listify(results["gap"])))
        if results["flashing"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} flashing lines: {}".format(len(results["flashing"]), listify(results["flashing"])))
        if results["hard to read"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} hard to read lines: {}".format(len(results["hard to read"]), listify(results["hard to read"])))
        if results["unreadable"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} unreadable lines: {}".format(len(results["unreadable"]), listify(results["unreadable"])))
        if results["negative duration"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} lines with negative duration (end before start): {}".format(len(results["negative duration"]), listify(results["negative duration"])))
        if results["jdpsetting"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} lines containing jdpsetting: {}".format(len(results["jdpsetting"]), listify(results["jdpsetting"])))
        if results["brainchild"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} brainchildesque lines: {}".format(len(results["brainchild"]), listify(results["brainchild"])))
        if not results["sorted"]:
            irc.msg(channel, u"\u0002\u000305ERROR: SCRIPT IS NOT SORTED BY START TIME! WHAT THE FUCK ARE YOU DOING?!\u000F")
        if not results["dialogue"]:
            irc.msg(channel, u"\u0002\u000305ERROR: SCRIPT HAS NO DIALOGUE! WHO THE FUCK DO YOU THINK YOU ARE, TRICHINAS?!\u000F")

        if (results["malformed"] or results["malformed comments"] or results["disjointed"] or results["italic fail"] or
            results["flashing"] or results["redundant"] or results["negative duration"] or results["overlap"] or
            results["brainchild"] or not results["sorted"] or not results["dialogue"]):
            raise manager.exception(u"Aborted creating xdelta for {}: Error occured in QC. Use `.errors [line number] [filename]` for more info.".format(show.name.english))

    # Step 5b: Break Haali Splitter
    #with open(os.path.join(guid, script), "r") as f:
    #    lines = f.readlines()
    #found_events = False
    #for i, line in enumerate(lines):
    #    if not found_events:
    #        if line.strip() == "[Events]":
    #            found_events = True
    #        continue
    #    if line.startswith("Format: "):
    #        keys = [k.strip() for k in line[8:].split(",")]
    #        break
    #if keys:
    #    d = {
    #        "Layer": "0",
    #        "Start": "0:00:00.00",
    #        "End": "0:00:00.00",
    #        "Style": "Default",
    #        "Name": "",
    #        "MarginL": "0",
    #        "MarginR": "0",
    #        "MarginV": "0",
    #        "Effect": "",
    #        "Text": "Haali Splitter a shit. " * 11400
    #    }
    #    lines.insert(i+1, "Comment: {}\n".format(",".join([d[k] if k in d else "" for k in keys])))
    #    with open(os.path.join(guid, script), "w") as f:
    #        f.write("".join(lines))

    # Step 6: MKVMerge
    match = re.search("(v\d+)", script)
    version = match.group(1) if match is not None else ""
    arguments = ["-o", os.path.join(guid, fname)]
    if not no_chapters:
        arguments.extend(["--no-chapters", "--chapters", os.path.join(guid, chapters)])
    for font in fonts:
        arguments.extend(["--attachment-mime-type", "application/x-truetype-font", "--attach-file", os.path.join(guid, font)])
    arguments.extend([os.path.join(guid, premux), "--compression", "0:zlib", os.path.join(guid, script)])
    arguments.extend(["--title", u"[{}] {} - {:02d}{}".format(group, title, episode, version)])
    arguments.extend(["--language", "0:ja"])
    arguments.extend(["--language", "1:ja"])
    arguments.extend(["--language", "2:en"])
    manager.dispatch("update", guid, u"Merging premux, script, chapters, and fonts")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("mkvmerge"), args=arguments, env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't merge premux and script.".format(show.name.english))
    irc.notice(user, u"Merged premux and script")

    # Step 7: Force CRC
    try:
        with open(os.path.join(guid, fname), "r+b") as f:
            f.seek(4224, 0)
            f.write("SERVRHE")
    except:
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't watermark completed file.".format(show.name.english))

    if crc is not None:
        manager.master.modules["crc"].patch(os.path.join(guid, fname), crc, 4232)

    # Step 8: Determine filename
    try:
        with open(os.path.join(guid, fname), "rb") as f:
            crc = binascii.crc32(f.read()) & 0xFFFFFFFF
    except:
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't open completed file for CRC verification.".format(show.name.english))

    if roman:
        version = "v{}".format(int_to_roman(int(version[:1]))) if version else ""
        episode = manager.master.modules["utils"].intToRoman(episode)
        crc = manager.master.modules["utils"].intToRoman(crc)
        nfname = u"[{}] {} - {}{} [{}].mkv".format(group, title, episode, version, crc)
    else:
        nfname = u"[{}] {} - {:02d}{} [{:08X}].mkv".format(group, title, episode, version, crc)
    nfname = nfname.replace(u"/", u" \u2044 ")
    os.rename(os.path.join(guid, fname).encode("utf8"), os.path.join(guid, nfname).encode("utf8"))
    fname = nfname
    irc.msg(channel, u"Determined final filename to be {}".format(fname))

    # Step 9: Make that xdelta
    xdelta = script + ".xdelta"
    manager.dispatch("update", guid, u"Generating xdelta")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("xdelta3"), args=["-f","-e","-s", os.path.join(guid, premux), os.path.join(guid, fname).encode("utf8"), os.path.join(guid, xdelta).encode("utf8")], env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't create xdelta.".format(show.name.english))
    irc.notice(user, u"Made xdelta")

    # Step 10: Upload that xdelta
    manager.dispatch("update", guid, u"Uploading xdelta")
    yield manager.master.modules["ftp"].put(guid, xdelta, folder)
    yield manager.master.modules["ftp"].upload(folder)
    irc.msg(channel, u"xdelta for {} uploaded".format(show.name.english))

    returnValue(fname)
