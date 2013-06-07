from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".block [name] || .block kyhz || Prevents person from using any commands.",
    "reverse_help": ".unblock [name] || .unblock shurt || Let's them use commands again"
}

def command(guid, manager, irc, channel, user, name, reverse = False, admin_mode = False):
    alias = yield manager.master.modules["alias"].resolve(name)
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
    yield manager.config.set("admins", admins)

    listing = u", ".join(admins["banned"])
    say(u"Banned users: {}".format(listing))
    returnValue(listing)
