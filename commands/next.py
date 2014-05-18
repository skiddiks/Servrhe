from twisted.internet.defer import inlineCallbacks

config = {
    "access": "public",
    "help": ".next [show name] || .next Accel World || Reports airing ETA for a show"
}

def command(guid, manager, irc, channel, user, show):
    show = manager.master.modules["showtimes"].resolve(show)
    manager.dispatch("update", guid, u"Waiting on showtimes.next")
    data = yield manager.master.modules["showtimes"].next(show)

    if data.episode == "finished":
        irc.msg(channel, u"The last episode of {} ({}) finished airing {} ago.".format(data.name.english, data.name.japanese, data.when))
    else:
        irc.msg(channel, u"Episode {} of {} ({}) will air in {}.".format(data.episode, data.name.english, data.name.japanese, data.when))
