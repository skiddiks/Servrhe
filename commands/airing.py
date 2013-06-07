from datetime import datetime as dt

config = {
    "access": "public",
    "help": ".airing || .airing || Lists the shows airing in the next 24 hours"
}

def command(guid, manager, irc, channel, user):
    now = dt.utcnow()
    shows = []
    ret = []
    for show in manager.master.modules["showtimes"].shows.values():
        if show.episode.current == show.episode.total:
            continue
        diff = dt.utcfromtimestamp(show.airtime) - now
        if diff.days == 0:
            shows.append((diff, show.name.english, show.channel))
    shows.sort(key=lambda s: s[0])
    if not shows:
        irc.msg(channel, u"No shows airing in the next 24 hours")
    for s in shows:
        when = manager.master.modules["utils"].dt2ts(s[0])
        irc.msg(channel, u"{} will finish airing in {} on {}".format(s[1], when, s[2]))

    return u", ".join([s[1] for s in shows])
