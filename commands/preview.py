from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import os, re

config = {
    "access": "admin",
    "help": ".preview [show] (--previous) || .preview prince || Generates a preview image"
}

def command(guid, manager, irc, channel, user, show, previous = False):
    show = manager.master.modules["showtimes"].resolve(show)

    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset

    folder = "/{}/{:02d}/".format(show.folder.ftp, episode)
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")
    yield manager.master.modules["ftp"].getFromCache(folder, premux, guid)

    try:
        preview = yield manager.master.modules["ftp"].getLatest(folder, "*.png")
        yield manager.master.modules["ftp"].get(folder, preview, guid)
        os.rename(os.path.join(guid, preview), os.path.join(guid, "preview.png"))

    except manager.exception:
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

        time = chapters["part a"]["start"] if "part a" in chapters else sorted(chapters.values(), key=lambda x: x["length"], reverse=True)[0]["start"]
        time += 30000
        time = manager.master.modules["subs"].intToTime(time, short=True)

        out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("ffmpeg"), args=["-ss", time, "-i", os.path.join(guid, premux), "-vframes", "1", os.path.join(guid, "preview.png")], env=os.environ)

        if code != 0:
            manager.log(out)
            manager.log(err)
            raise manager.exception(u"Aborted previewing {}: Couldn't generate preview image.".format(show.name.english))

    try:
        with open(os.path.join(guid, "preview.png"), "rb") as f:
            preview = {"name": premux+".png", "data": f.read()}
    except IOError:
        raise manager.exception(u"Aborted previewing {}: Couldn't open preview image.".format(show.name.english))

    img_link = yield manager.master.modules["blog"].uploadImage(**preview)

    irc.msg(channel, img_link)

    returnValue(img_link)
