config = {
    "access": "public",
    "help": ".whyarentwedoing [show name] || .whyarentwedoing Symphogear S3 || Tells you a good reason why we aren't doing a show"
}

def command(guid, manager, irc, channel, user, showname):
    try:
        show = manager.master.modules["showtimes"].resolve(showname)
        irc.msg(channel, u"But... we ARE doing \"{}\"!".format(show.name.english))
    except:
        irc.msg(channel, u"We aren't doing \"{}\" because herkz is a shit".format(showname))
