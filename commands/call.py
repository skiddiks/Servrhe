config = {
    "access": "admin",
    "help": ".call [name] [message] || .call release Sup release? || Calls somebody and says the message to them"
}

def command(guid, manager, irc, channel, user, name, message):
    alias = yield manager.master.modules["alias"].resolve(name)
    number = manager.master.modules["twilio"].resolve(alias)
    id = yield manager.master.modules["twilio"].call(number, user, message)
    irc.msg(channel, u"Calling {}... (ID #{})".format(alias, id))
