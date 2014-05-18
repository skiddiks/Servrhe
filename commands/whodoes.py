from twisted.internet.defer import returnValue

config = {
    "access": "public",
    "help": ".whodoes (position) [show name] || .whodoes timer Accel World || Reports who does a job for a show"
}

def command(guid, manager, irc, channel, user, show):
    manager.dispatch("update", guid, u"Waiting on showtimes.getPosition")

    try:
        position, _, newshow = show.partition(" ")
        position = yield manager.master.modules["showtimes"].getPosition(position)
        show = newshow
    except:
        position = None

    show = manager.master.modules["showtimes"].resolve(show)

    if position:
        name = getattr(show, position).name if position != "encoder" else "UNKNOWN"
        irc.msg(channel, u"{} is the {} for {}".format(name, position, show.name.english))
        returnValue(name)
    else:
        positions = yield manager.master.modules["showtimes"].config.get("positions")
        staff = u", ".join([u"{}: {}".format(p, getattr(show, p).name) for p in positions if p != "encoder"])
        irc.msg(channel, u"\u0002Staff for {}:\u000F {}".format(show.name.english, staff))        
