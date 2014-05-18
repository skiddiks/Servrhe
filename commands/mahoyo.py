from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import os, re

config = {
    "access": "admin",
    "help": ".mahoyo || .mahoyo || Updates mahoyo progress on blog and in topic.",
}

def command(guid, manager, irc, channel, user):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    manager.dispatch("update", guid, u"Updating SVN repository")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("svn"), args=["up", "mahoyo"], env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted updating mahoyo progress: Couldn't update SVN")

    manager.dispatch("update", guid, u"Counting progress")
    args = "mahoyo/tools/mahouyo.py count -r mahoyo/scripts/raw/ -t mahoyo/scripts/translated/ -i mahoyo/scripts/inserted/ -f html -o mahoyo/count".split(" ")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("python"), args=args, env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted updating mahoyo progress: Couldn't count progress")

    with open("mahoyo/count.html", "r") as f:
        progress = f.read()
    percentage = float(re.findall("\d+\.\d+%", progress)[-1][:-1])

    # Silently die if nothing happened
    manager.dispatch("update", guid, u"Fetching current progress")
    current = yield manager.master.modules["showtimes"].config.get("topic", {"percentage": 0, "text": None})
    if percentage == current["percentage"]:
        irc.notice(user, u"No progress has been made, silently quitting")
        return

    irc.msg(channel, "Progress determined to be {:0.2f}%, updating blog and topic now.".format(percentage))

    manager.dispatch("update", guid, u"Updating Blog")
    yield manager.master.modules["blog"].updateMahoyo(progress)

    manager.dispatch("update", guid, u"Updating Topic")
    yield manager.master.modules["showtimes"].setPercentage(percentage)
    yield manager.master.modules["showtimes"].updateTopic()

    returnValue("{:0.2f}%".format(percentage))
