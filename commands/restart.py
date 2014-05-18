from twisted.internet import reactor

config = {
    "access": "superadmin",
    "help": ".restart || .restart || Restart the bot"
}

def command(guid, manager, irc, channel, user):
    reactor.stop()
