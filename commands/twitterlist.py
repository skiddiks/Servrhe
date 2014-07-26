config = {
    "access": "admin",
    "help": ".twitterlist || .twitterlist || Lists twitter accounts that can be used for Nyaa descriptions"
}

def command(guid, manager, irc, channel, user):
    twitters = yield manager.master.modules["config"].get("nyaa", "twitter", {"jdp": "johnnydickpants"})
    twitters = sorted(twitters.items())

    while twitters:
        o, twitters = twitters[:5], twitters[5:]
        irc.notice(user, u", ".join([u"{} -> @{}".format(k, v) for k, v in o]))
