from twisted.internet.defer import returnValue
import datetime

config = {
    "access": "public",
    "help": ".duwang (--seed=SEED) || .duwang jojo || what a beautiful Duwang"
}

cooldowns = {}

def command(guid, manager, irc, channel, user, seed = None):
    permissions = yield manager.getPermissions(user)
    now = datetime.datetime.utcnow()

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

    cooldowns[user]["time"] = now + cooldown
    cooldowns[user]["warnings"] = 0
    message = manager.master.modules["duwang"].ramble(seed)
    irc.msg(channel, message)
    returnValue(message)
