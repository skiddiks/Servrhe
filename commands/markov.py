from twisted.internet.defer import returnValue
import datetime

config = {
    "access": "public",
    "help": ".markov (--name=NAME) (--seed=SEED) (--duwang) || .markov foogi || Ramble as [name] would, utilizing markov chains"
}

cooldowns = {}

def command(guid, manager, irc, channel, user, name = None, seed = None, duwang = False):
    irc.msg(channel, u"Markov has been disabled due to being a dumb feature that I'm sick of dealing with")
    return

    manager.dispatch("update", guid, u"Waiting on manager.getPermissions")
    permissions = yield manager.getPermissions(user)
    now = datetime.datetime.utcnow()

    if name is True:
        name = None
    if seed is True:
        seed = None

    if name is not None and " " in name:
        name = name.split(" ")[0]
    if seed is not None and " " in seed:
        seed = seed.split(" ")[0]

    if "staff" in permissions:
        cooldown = datetime.timedelta(minutes=0)
    else:
        cooldown = datetime.timedelta(minutes=3)

    if user not in cooldowns:
        cooldowns[user] = {
            "time": now,
            "warnings": 0,
            "kicks": 0
        }
    if cooldowns[user]["time"] > now:
        if cooldowns[user]["warnings"] >= 5 or cooldowns[user]["kicks"] >= 10:
            cooldowns[user]["warnings"] = 0
            cooldowns[user]["kicks"] = 0
            irc.kickban(channel, user, u"Markov command abuse")
        elif cooldowns[user]["warnings"] >= 3:
            cooldowns[user]["kicks"] += 1
            irc.kick(channel, user, u"Markov command abuse")
        else:
            cooldowns[user]["warnings"] += 1
            diff = manager.master.modules["utils"].dt2ts(cooldowns[user]["time"] - now)
            irc.notice(user, u"You just used this command, please wait {} before using it again.".format(diff))
        return

    if not name:
        cooldowns[user]["time"] = now + cooldown
        cooldowns[user]["warnings"] = 0
        manager.dispatch("update", guid, u"Generating sentence")
        message = yield manager.master.modules["markov"].ramble(seed=seed, entropy=duwang)
        irc.msg(channel, message)
        return

    manager.dispatch("update", guid, u"Waiting on manager.getPermissions")
    otherperms = yield manager.getPermissions(name)
    if "staff" in otherperms and "staff" not in permissions:
        cooldown *= 5

    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    name = yield manager.master.modules["alias"].resolve(name)
    if name not in manager.master.modules["markov"].ranking:
        raise manager.exception(u"No data on {}".format(name))

    cooldowns[user]["time"] = now + cooldown
    cooldowns[user]["warnings"] = 0
    manager.dispatch("update", guid, u"Generating sentence")
    message = yield manager.master.modules["markov"].ramble(name, seed, duwang)
    irc.msg(channel, message)
    returnValue(message)
