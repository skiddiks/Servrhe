from twisted.internet.defer import returnValue

config = {
    "access": "public",
    "help": ".ranking || .ranking || Get your ranking"
}

def command(guid, manager, irc, channel, user):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    name = yield manager.master.modules["alias"].resolve(user)
    ranking = manager.master.modules["markov"].ranking
    rank = ranking[name]
    better = sorted(ranking.values(), key=lambda x: x["rank"])[rank["rank"]-2] if rank["rank"] > 1 else False

    message = u"Beating you is {} with {:,d} lines.".format(better["name"], better["lines"]) if better else u"You're in the lead, congrats."
    message = u"You are rank #{:,d} with {:,d} lines. {}".format(rank["rank"], rank["lines"], message)

    irc.msg(channel, message)
    returnValue(message)
