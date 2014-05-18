config = {
    "access": "admin",
    "help": ".sendtobootcamp [person] || .sendtobootcamp foogiman || Gives a user access to bootcamp"
}

def command(guid, manager, irc, channel, user, victim):
    c = yield manager.config.get("bootcamp_channel")
    p = yield manager.config.get("bootcamp_password")
    irc.notice(victim, u"Please join {} with the password \"{}\".".format(c, p))
