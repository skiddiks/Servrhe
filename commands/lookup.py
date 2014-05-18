from twisted.internet.defer import returnValue

config = {
    "access": "public",
    "help": ".lookup [word] || .lookup discharge || List who said the word how many times"
}

def command(guid, manager, irc, channel, user, word):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    word, _, _ = word.partition(" ")
    counts = yield manager.master.modules["markov"].count(word)
    counts = u", ".join([u"{} - {:,d} times".format(i[0], i[1]) for i in counts.most_common(5)])
    message = u"People who have said \"{}\" the most: {}".format(word, counts)
    irc.msg(channel, message)
    returnValue(message)
