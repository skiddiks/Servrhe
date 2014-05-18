config = {
    "access": "owner",
    "help": ".exec [code] || .exec irc.msg(channel, u'Orcus is a faggot') || Runs arbitrary python code as root"
}

def command(guid, manager, irc, channel, user, code):
    exec(code)
