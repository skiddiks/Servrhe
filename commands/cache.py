from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".cache [showname] (--previous) || .cache eotena || Caches everything for a show so that other commands work faster"
}

def command(guid, manager, irc, channel, user, show, previous = False):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset
    folder = "{}/{:02d}".format(show.folder.ftp, episode)
    
    irc.msg(channel, u"Caching {}".format(folder))
    manager.dispatch("update", guid, u"Caching {}".format(folder))
    yield manager.master.modules["ftp"].download(folder)

    irc.msg(channel, u"{} cached.".format(folder))

    returnValue(folder)
