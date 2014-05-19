config = {
    "access": "admin",
    "help": ".addressbook || .addressbook || List users who we have phone numbers for"
}

def command(guid, manager, irc, channel, user):
    numbers = yield manager.master.modules["db"].numberList()
    irc.notice(user, u"We have numbers for: {}".format(u", ".join(sorted(numbers.keys()))))
