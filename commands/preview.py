from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
from bs4 import BeautifulSoup
import os, re

config = {
    "access": "admin",
    "help": ".preview [show] (--previous) (--preview=TIME) (--webm=DURATION) || .preview prince || Generates a preview image. TIME can be a frame number, HH:MM:SS.MM (must contain period), CHAPTER+SS.MM (chapter should match exactly), or FTP to force an ftp download."
}

def command(guid, manager, irc, channel, user, show, previous = False, preview = None, webm = None):
    show = manager.master.modules["showtimes"].resolve(show)

    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset

    if preview is not None:
        preview = preview.lower()

    if webm is True:
        webm = 3.0 # Defaults to 3 seconds
    elif webm:
        try:
            webm = float(webm)
        except:
            raise manager.exception(u"--webm must be the number of seconds the preview should last for. Got \"{}\" instead.".format(webm))

    folder = "{}/{:02d}".format(show.folder.ftp, episode)
    manager.dispatch("update", guid, u"Caching {}".format(folder))
    yield manager.master.modules["ftp"].download(folder)

    manager.dispatch("update", guid, u"Determining last modified mkv file")
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")

    manager.dispatch("update", guid, u"Downloading {}".format(premux))
    yield manager.master.modules["ftp"].get(folder, premux, guid)

    ftp = False
    for ext in ["jpg", "jpeg", "png", "gif"]:
        try:
            manager.dispatch("update", guid, u"Determining last modified {} file".format(ext))
            preview_image = yield manager.master.modules["ftp"].getLatest(folder, "*.{}".format(ext))
            preview_ext = ext
            manager.dispatch("update", guid, u"Downloading".format(preview_image))
            yield manager.master.modules["ftp"].get(folder, preview_image, guid)
            os.rename(os.path.join(guid, preview_image), os.path.join(guid, "preview.{}".format(ext)))
            ftp = True
            break
        except manager.exception:
            continue

    if preview == "ftp" and not ftp:
        raise manager.exception(u"Aborted releasing {}: Couldn't find preview image on FTP".format(show.name.english))

    if not ftp or (preview is not None and preview != "ftp"):
        if preview is None or "+" in preview:
            try:
                manager.dispatch("update", guid, u"Determining last modified xml file")
                chapters = yield manager.master.modules["ftp"].getLatest(folder, "*.xml")

                manager.dispatch("update", guid, u"Downloading {}".format(chapters))
                yield manager.master.modules["ftp"].get(folder, chapters, guid)
                with open(os.path.join(guid, chapters), "r") as f:
                    soup = BeautifulSoup(f.read(), "xml", from_encoding="utf8")
                out = "\n".join(["CHAPTER{0:02d}={1}\nCHAPTER{0:02d}NAME={2}".format(index + 1, e.find("ChapterTimeStart").string.encode("utf8"), e.find("ChapterString").string.encode("utf8")) for index, e in enumerate(soup("ChapterAtom"))])

            except Exception as e:
                manager.dispatch("update", guid, u"Extracting chapters from premux")
                out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("mkvextract"), args=["chapters", "-s", os.path.join(guid, premux)], env=os.environ)

                if code != 0:
                    manager.log(out)
                    manager.log(err)
                    raise manager.exception(u"Aborted previewing {}: Couldn't extract chapters.".format(show.name.english))

            chapters = [l.partition("=")[2].lower() for l in out.split("\n")]
            chapters = [(n, {"start": manager.master.modules["subs"].timeToInt(t), "length": 0}) for n,t in zip(chapters[1::2], chapters[0::2])]
            for a, b in zip(chapters, chapters[1:]):
                a[1]["length"] = b[1]["start"] - a[1]["start"]
            chapters = dict(chapters)

            if not chapters:
                raise manager.exception(u"Aborted previewing {}: No chapters to make a preview image from.".format(show.name.english))

        if preview is None:
            time = chapters["part a"]["start"] if "part a" in chapters else sorted(chapters.values(), key=lambda x: x["length"], reverse=True)[0]["start"]
            time += 30000
        elif "." not in preview:
            conversion = float(24000) / 1001
            time = int(int(preview) / conversion * 1000)
        elif "+" not in preview:
            time = manager.master.modules["subs"].timeToInt(preview)
        else:
            chapter, _, offset = preview.partition("+")
            if chapter not in chapters:
                raise manager.exception(u"Aborted previewing {}: Requested chapter \"{}\" not found".format(show.name.english, chapter))
            time = chapters[chapter]["start"] + manager.master.modules["subs"].timeToInt(offset)

        if webm and preview is None:
            rough_time = manager.master.modules["subs"].intToTime(time, short=True)
            fine_time = "0.000"
        elif time > 20000:
            rough_time = manager.master.modules["subs"].intToTime(time - 20000, short=True)
            fine_time = "20.000"
        else:
            rough_time = "0.000"
            fine_time = manager.master.modules["subs"].intToTime(time, short=True)


        manager.dispatch("update", guid, u"Generating preview image")

        if webm:
            preview_ext = "webm"
            out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("avconv"), args=[
                "-ss", rough_time,
                "-i", os.path.join(guid, premux),
                "-ss", fine_time,
                "-t", "{:0.3f}".format(webm),
                "-threads", "4", # Speed up encoding with 4 threads
                "-c:v", "libvpx", # Use standard webm video codec
                "-an", # Disable audio
                "-b:v", "800K", # 800kbps is plenty
                "-vf", "scale=-1:360", # 360p is plenty
                os.path.join(guid, "preview.{}".format(preview_ext))
            ], env=os.environ)
        else:
            preview_ext = "jpg"
            extraargs = []
            if preview is None:
                extraargs.extend(["-vf", "select='eq(pict_type,I)'", "-vsync", "2"])
            #extraargs.extend(["-vf", "colormatrix=bt709:bt601"])
            out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("avconv"), args=[
                "-ss", rough_time,
                "-i", os.path.join(guid, premux),
                "-ss", fine_time
            ] + extraargs + [
                "-vframes", "1",
                os.path.join(guid, "preview.{}".format(preview_ext))
            ], env=os.environ)

        if code != 0:
            manager.log(out)
            manager.log(err)
            raise manager.exception(u"Aborted previewing {}: Couldn't generate preview image.".format(show.name.english))

        try:
            manager.dispatch("update", guid, u"Determining last modified ass file")
            script = yield manager.master.modules["ftp"].getLatest(folder, "*.ass")
        except:
            script = None

        if script is not None:
            manager.dispatch("update", guid, u"Downloading {}".format(script))
            yield manager.master.modules["ftp"].get(folder, script, guid)
            hovertext = manager.master.modules["subs"].getBestLine(guid, script, time)
            if hovertext is not None:
                irc.msg(channel, "Best line at given time: {}".format(hovertext))
            else:
                irc.msg(channel, "No lines spoken at given time")
        else:
            irc.msg(channel, "No script on FTP to find a line from")

    try:
        with open(os.path.join(guid, "preview.{}".format(preview_ext)), "rb") as f:
            preview = {"name": (u"{}.{}".format(premux, preview_ext)).encode("utf8"), "data": f.read()}
    except IOError:
        raise manager.exception(u"Aborted previewing {}: Couldn't open preview image.".format(show.name.english))

    manager.dispatch("update", guid, u"Uploading {} to blog".format(preview["name"]))
    img_link = yield manager.master.modules["blog"].uploadImage(**preview)

    manager.dispatch("update", guid, u"Uploading preview image to FTP")
    yield manager.master.modules["ftp"].put(guid, u"preview.{}".format(preview_ext), folder)
    yield manager.master.modules["ftp"].upload(folder)

    irc.msg(channel, "Preview image: {}".format(img_link))

    returnValue(img_link)
