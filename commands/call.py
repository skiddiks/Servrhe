config = {
    "access": "admin",
    "help": ".call [name] [message] || .call release Sup release? || Calls somebody and says the message to them"
}

def command(guid, manager, irc, channel, user, name, message):
    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    alias = yield manager.master.modules["alias"].resolve(name)
    number = yield manager.master.modules["twilio"].resolve(alias)
    manager.dispatch("update", guid, u"Waiting on twilio.call")
    id = yield manager.master.modules["twilio"].call(number, user, message)
    irc.msg(channel, u"Calling {}... (ID #{})".format(alias, id))
