config = {
    "access": "admin",
    "help": ".text [name] [message] || .text release Sup release? || Text somebody the message"
}

def command(guid, manager, irc, channel, user, name, message):
    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    alias = yield manager.master.modules["alias"].resolve(name)
    number = yield manager.master.modules["twilio"].resolve(alias)
    manager.dispatch("update", guid, u"Waiting on twilio.text")
    id = yield manager.master.modules["twilio"].text(number, user, message)
    irc.msg(channel, u"Texting {}... (ID #{})".format(alias, id))
