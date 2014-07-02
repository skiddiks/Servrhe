config = {
    "access": "admin",
    "help": ".twitteradd [name] [twitter handle] || .twitteradd jdp jdpls || Adds user to twitter list"
}

def command(guid, manager, irc, channel, user, name, handle):
    twitters = yield manager.master.modules["config"].get("nyaa", "twitter", {"jdp": "johnnydickpants"})

    if name in twitters:
        raise manager.exception(u"\"{}\" is already in the twitter list".format(name))

    if handle in twitters.values():
        raise manager.exception(u"\"@{}\" is already in the twitter list".format(handle))

    twitters[name] = handle
	yield manager.master.modules["config"].set("nyaa", "twitter", twitters)
