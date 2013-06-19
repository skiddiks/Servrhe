from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import binascii, fnmatch, os, re

config = {
    "access": "admin",
    "help": ".xdelta [show name] (--previous) (--no-chapters) (--no-qc) (--roman) (--crc=HEX) || Creates an xdelta for the current episode of the show. Requires an .mkv, .ass and .xml file. --previous re-muxes the last released episode. --no-chapters skips chapter muxing. --roman uses numerals for the episode number & CRC."
}

def command(guid, manager, irc, channel, user, show, previous = False, no_chapters = False, no_qc = False, roman = False, crc = None):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset
    fname = "test.mkv"

    if crc is not None and re.match("[0-9a-fA-F]{8}", crc) is None:
        raise manager.exception(u"Invalid CRC")

    # Step 1: Search FTP for premux + script
    folder = "/{}/{:02d}/".format(show.folder.ftp, episode)
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")
    script = yield manager.master.modules["ftp"].getLatest(folder, "*.ass")
    if not no_chapters:
        chapters = yield manager.master.modules["ftp"].getLatest(folder, "*.xml")

    # Step 2: Download that shit
    yield manager.master.modules["ftp"].getFromCache(folder, premux, guid)
    yield manager.master.modules["ftp"].get(folder, script, guid)
    if not no_chapters:
        yield manager.master.modules["ftp"].get(folder, chapters, guid)
        irc.msg(channel, u"Found premux, script and chapters: {}, {} and {}".format(premux, script, chapters))
    else:
        irc.msg(channel, u"Found premux and script: {} and {}".format(premux, script))

    # Step 3: Download fonts
    yield manager.master.modules["ftp"].uploadFonts(folder)
    fonts = yield manager.master.modules["ftp"].downloadFonts(folder, guid)
    irc.notice(user, u"Fonts downloaded")

    # Step 4: Verify fonts
    needed_fonts = manager.master.modules["subs"].getFonts(guid, script)
    available_fonts = set()
    for font in fonts:
        name = manager.master.modules["subs"].getFontName(guid, font)
        if name:
            available_fonts.add(name)
    remaining_fonts = needed_fonts - available_fonts
    if remaining_fonts:
        required = ", ".join(list(remaining_fonts))
        required = required.decode("utf8")
        raise manager.exception(u"Aborted creating xdelta for {}: Missing fonts: {}. (Got: {})".format(show.name.english, required, u", ".join(fonts)))

    # Step 5: QC
    if not no_qc:
        listify = lambda l: ", ".join([str(n) for n in l[:20]] + ["..."] if len(l) > 20 else [str(n) for n in l])
        results = manager.master.modules["subs"].qc(guid, script)
        # Colors: INFO = 12 (blue), WARNING = 8 (orange), ERROR = 5 (red)
        irc.msg(channel, u"\u0002\u000312INFO:\u000F Total Lines: {:,d}, Comments: {:,d}, Dialogue: {:,d}, Signs: {:,d}, OP: {:,d}, ED: {:,d}".format(results["total"], results["comments"], results["dialogue"], results["signs"], results["OP"], results["ED"]))
        irc.msg(channel, u"\u0002\u000312INFO:\u000F Linebreaks in dialogue: {:,d}, Italics in dialogue: {:,d}, Honorifics in dialogue: {:,d}, Zero length lines: {:,d}".format(len(results["linebreaks"]), len(results["italics"]), len(results["honorifics"]), len(results["zero length"])))
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
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} dialoge lines containing double spaces: {}".format(len(results["double space"]), listify(results["double space"])))
        if results["jdpsetting"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} lines containing jdpsetting: {}".format(len(results["jdpsetting"]), listify(results["jdpsetting"])))
        if results["malformed"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} malformed tags: {}".format(len(results["malformed"]), listify(results["malformed"])))
        if results["disjointed"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} disjointed tags: {}".format(len(results["disjointed"]), listify(results["disjointed"])))
        if results["overlap"]:
            irc.msg(channel, u"\u0002\u000305ERROR:\u000F {:,d} overlapping lines: {}".format(len(results["overlap"]), listify(results["overlap"])))
        if results["gap"]:
            irc.msg(channel, u"\u0002\u000308WARNING:\u000F {:,d} flashing lines: {}".format(len(results["gap"]), listify(results["gap"])))

        if results["malformed"] or results["disjointed"] or results["overlap"]:
            raise manager.exception(u"Aborted creating xdelta for {}: Error occured in QC.".format(show.name.english))

    # Step 6: MKVMerge
    arguments = ["-o", os.path.join(guid, fname)]
    if not no_chapters:
        arguments.extend(["--no-chapters", "--chapters", os.path.join(guid, chapters)])
    for font in fonts:
        arguments.extend(["--attachment-mime-type", "application/x-truetype-font", "--attach-file", os.path.join(guid, font)])
    arguments.extend([os.path.join(guid, premux), os.path.join(guid, script)])
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
    match = re.search("(v\d+).ass", script)
    version = match.group(1) if match is not None else ""
    try:
        with open(os.path.join(guid, fname), "rb") as f:
            crc = binascii.crc32(f.read()) & 0xFFFFFFFF
    except:
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't open completed file for CRC verification.".format(show.name.english))

    if roman:
        version = "v{}".format(int_to_roman(int(version[:1]))) if version else ""
        episode = manager.master.modules["utils"].intToRoman(episode)
        crc = manager.master.modules["utils"].intToRoman(crc)
        nfname = u"[Commie] {} - {}{} [{}].mkv".format(show.name.english, episode, version, crc)
    else:
        nfname = u"[Commie] {} - {:02d}{} [{:08X}].mkv".format(show.name.english, episode, version, crc)
    os.rename(os.path.join(guid, fname), os.path.join(guid, nfname))
    fname = nfname
    irc.msg(channel, u"Determined final filename to be {}".format(fname))

    # Step 9: Make that xdelta
    xdelta = script.replace(".ass",".xdelta")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("xdelta3"), args=["-f","-e","-s", os.path.join(guid, premux), os.path.join(guid, fname), os.path.join(guid, xdelta)], env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted creating xdelta for {}: Couldn't create xdelta.".format(show.name.english))
    irc.notice(user, u"Made xdelta")

    # Step 10: Upload that xdelta
    yield manager.master.modules["ftp"].put(guid, xdelta, folder)
    irc.msg(channel, u"xdelta for {} uploaded".format(show.name.english))

    returnValue(fname)
