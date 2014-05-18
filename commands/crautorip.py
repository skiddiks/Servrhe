from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".crautorip [contents] [quality] [series] || Contents is subs, video or both. Quality is 360, 480, 720, or 1080. Series uses CR's naming"
}

def command(guid, manager, irc, channel, user, contents, quality, show):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    if contents not in ("subs","video","both"):
        raise manager.exception("Invalid content, must be subs, video or both")

    if quality not in ("360", "480", "720", "1080"):
        raise manager.exception("Invalid quality, must be 360, 480, 720, or 1080")

    show = manager.master.modules["crunchy"].resolve(show)

    subs = contents in ("subs", "both")
    video = contents in ("video", "both")
    yield manager.master.modules["crunchy"].autodownload(show, quality, video, subs)
    irc.msg(channel, u"Set {} to autorip {} at {}p".format(show.name, contents, quality))

    returnValue(show.name)
