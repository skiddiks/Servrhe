from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".block [name] || .block kyhz || Prevents person from using any commands.",
    "reverse_help": ".unblock [name] || .unblock shurt || Let's them use commands again"
}

def command(guid, manager, irc, channel, user, name, reverse = False, admin_mode = False):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    alias = yield manager.master.modules["alias"].resolve(name)
    manager.dispatch("update", guid, u"Fetching admin list")
    admins = yield manager.config.get("admins", {})

    if admin_mode:
        say = lambda m: irc.msg(channel, m)
    else:
        say = lambda m: irc.notice(user, m)

    banned = set(admins["banned"] if "banned" in admins else [])

    if reverse:
        banned.discard(alias)
    else:
        banned.add(alias)

    admins["banned"] = list(banned)
    manager.dispatch("update", guid, u"Saving admin list")
    yield manager.config.set("admins", admins)

    listing = u", ".join(admins["banned"])
    say(u"Banned users: {}".format(listing))
    returnValue(listing)
