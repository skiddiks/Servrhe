config = {
    "access": "admin",
    "help": ".twitterremove [name] || .twitterremove jdp || Removes user from twitter list"
}

def command(guid, manager, irc, channel, user, name):
    twitters = yield manager.master.modules["config"].get("nyaa", "twitter", {"jdp": "johnnydickpants"})

    if name not in twitters:
        raise manager.exception(u"\"{}\" isn't in the twitter list".format(name))

    del twitters[name]
	yield manager.master.modules["config"].set("nyaa", "twitter", twitters)
