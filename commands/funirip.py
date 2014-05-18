from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".funirip [quality] [episode] [series] || Quality is 360, 480, or 720. Series uses CR's naming"
}

def command(guid, manager, irc, channel, user, quality, episode, show):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    if quality not in ("360", "480", "720"):
        raise manager.exception("Invalid quality, must be 360, 480, or 720")

    try:
        episode = int(episode)
    except:
        raise manager.exception("Invalid episode number, must be an integer")

    show = manager.master.modules["funi"].resolve(show)

    key = "{:02d}".format(episode)
    if key not in show.episodes:
        raise manager.exception("No data for that episode, try again when Funi has added it")

    data = show.episodes[key]

    irc.msg(channel, u"AIGHT M8, WE'LL GIT ZAT RIGHT UP READY FOR YA!")
    manager.dispatch("update", guid, u"Downloading {} {} [{}p]".format(show.name, key, quality))
    yield manager.master.modules["funi"].rip(guid, data, quality)
    irc.msg(channel, u"Ripping of {} {} [{}p] was successful".format(show.name, key, quality))
    
    returnValue(show.name)
