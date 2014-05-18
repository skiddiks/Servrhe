from twisted.internet.defer import returnValue

config = {
    "access": "admin",
    "help": ".daisuki [url] || Rips subs from url"
}

def command(guid, manager, irc, channel, user, url):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    irc.msg(channel, u"AIGHT M8, WE'LL GIT ZAT RIGHT UP READY FOR YA!")
    manager.dispatch("update", guid, u"Downloading {}".format(url))
    filename = yield manager.master.modules["daisuki"].rip(guid, url)
    irc.msg(channel, u"Ripping of {} was successful".format(filename))

    returnValue(filename)
