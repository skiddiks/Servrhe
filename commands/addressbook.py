config = {
    "access": "admin",
    "help": ".addressbook || .addressbook || List users who we have phone numbers for"
}

def command(guid, manager, irc, channel, user):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    irc.notice(user, u"We have numbers for: {}".format(u", ".join(manager.master.modules["twilio"].numbers.keys())))
