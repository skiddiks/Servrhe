
config = {
    "access": "admin",
    "help": ".status || .status || List commands that are running."
}

def command(guid, manager, irc, channel, user):
	irc.msg(channel, u"\n".join(manager.master.modules["status"].list()))
