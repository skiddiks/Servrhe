from twisted.internet.defer import returnValue
config = {
    "access": "public",
    "help": ".commands || .commands || Lists available commands"
}

def command(guid, manager, irc, channel, user):
    manager.dispatch("update", guid, u"Waiting on manager.getPermissions")
    permissions = yield manager.getPermissions(user)
    r = []
    for command in manager.commands.values():
        if command["access"] in permissions:
            r.append(command["name"])
            if "reverse" in command["kwargs"]:
                r.append("un{}".format(command["name"]))
    r.sort()
    irc.msg(channel, u"Available commands: {}".format(" ".join(r)))

    returnValue(u" ".join(r))
