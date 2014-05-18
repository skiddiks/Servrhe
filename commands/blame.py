from twisted.internet.defer import returnValue
from datetime import datetime as dt
from datetime import timedelta as td
import random, fnmatch

config = {
    "access": "public",
    "help": ".blame [show name] || .blame Accel World || Reports who is to blame for a show not being released"
}

def command(guid, manager, irc, channel, user, show):
    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    alias = yield manager.master.modules["alias"].resolve(user)
    show = manager.master.modules["showtimes"].resolve(show)
    manager.dispatch("update", guid, u"Waiting on showtimes.substatus")
    data = yield manager.master.modules["showtimes"].substatus(show)

    #updated = show.airtime + 30*60 if data.position in ["encoder","translator"] else data.updated
    updated = dt.utcnow() - dt.utcfromtimestamp(data.updated)
    updated += td(hours=4) # ?????? Why do I have to do this???
    when = manager.master.modules["utils"].dt2ts(updated)
    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    worker = yield manager.master.modules["alias"].resolve(data.name)
    toblame = manager.master.modules["utils"].antihighlight(data.name)

    # Revenge on DxS
    #worker == "dxs"
    #insults = [
    #    u"Please ask him why he's such a slow scumbag!",
    #    u"Feel free to insult his mother's choice to not have an abortion!",
    #    u"Go ahead and vent your anger at his inability to do anything properly!",
    #    u"ETA: The heat death of the universe.",
    #    u"Enjoy having your favorite show ruined!",
    #    u"Why do you bother holding out hope?",
    #    u"Truly a master of being worthless!",
    #    u"One day he might be useful, but not today."
    #]

    if data.position == "completed" and data.name == "completed":
        irc.msg(channel, u"{} is completed as of {} ago.".format(show.name.english, when))
    elif data.position == "DROPPED" and data.value == "DROPPED":
        irc.msg(channel, u"{} has been dropped at episode {:02d} as of {} ago.".format(show.name.english, data.episode, when))
    elif alias == worker:
        irc.msg(channel, u"Why are YOU asking? You know you've delayed episode {:02d} of {} for {}. Get on it!".format(data.episode, show.name.english, when))
    else:
        message = u"Episode {:02d} of {} is at the {}, {}, as of {} ago.".format(data.episode, show.name.english, data.position, toblame, when)

        if data.position == "timer":
            for o in sorted(manager.master.modules["progress"].reports.values(), key=lambda x: x["updated"], reverse=True):
                if fnmatch.fnmatch("{} {:02d}".format(show.name.english.lower(), data.episode).lower(), "*" + o["script"].replace(" ", "*").lower()): # Is the script name in the series name?
                    message += u" ({:03d} / {:03d} lines completed)".format(o["completed"], o["total"])
                    break

        irc.msg(channel, message)
        #irc.msg(channel, u"Episode {:02d} of {} is at the {}, DxS, as of {} ago. {}".format(data.episode, show.name.english, data.position, when, random.choice(insults)))

    returnValue(data.name)
