from twisted.internet.defer import returnValue

config = {
    "access": "public",
    "help": ".whatdo [person] || .whatdo foogiman || What things can this person do?"
}

def command(guid, manager, irc, channel, user, victim):
    if victim.startswith("."):
        raise manager.exception(u".kb {} don't try shit like that".format(user))

    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    victim = yield manager.master.modules["alias"].resolve(victim)
    uid = yield manager.master.modules["db"].alias2userId(victim)
    positions = set()
    shows = set()

    if victim == u"fugiman":
        positions.add(u"technowizard")
        shows.add(u"maintaining ServrheV5")

    elif victim == u"lae":
        positions.add(u"technowizard")
        shows.add(u"maintaining showtimes & the blog")

    elif victim == u"sunako":
        positions.add(u"pornomancer")
        shows.add(u"showing you a good time")

    elif victim == u"caex":
        victim = u".kb CaeX CaeX"
        positions.add(u"piece of shit")
        shows.add(u"getting akicked permanently")

    for show in manager.master.modules["showtimes"].shows.values():
        if show.episode.current == show.episode.total:
            continue

        for position in ["translator", "editor", "timer", "typesetter", "qc"]:
            blame = getattr(show, position)
            manager.dispatch("update", guid, u"Waiting on alias.resolve")
            staller = yield manager.master.modules["db"].alias2userId(blame.name)
            if staller == uid:
                positions.add(position)
                if show.name.abbreviation:
                    shows.add(show.name.abbreviation)
                else:
                    shows.add("".join([x[:3] for x in show.name.english.split()]))

    if not positions:
        raise manager.exception(u"{} is useless.".format(victim))

    positions = sorted(list(positions))
    shows = filter(None, sorted(list(shows)))
    grammer_nazi = u"an" if positions[0].startswith("e") else u"a"
    positions = u"{} and {}".format(u", ".join(positions[:-1]), positions[-1]) if len(positions) > 1 else positions[0]
    shows = u"{} and {}".format(u", ".join(shows[:-1]), shows[-1]) if len(shows) > 1 else shows[0]

    irc.msg(channel, u"{} is {} {} working on {}".format(victim, grammer_nazi, positions, shows))
    returnValue(victim)
