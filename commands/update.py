from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import os, re

config = {
    "access": "superadmin",
    "help": ".update || .update || Pulls in latest changes from github.",
}

def command(guid, manager, irc, channel, user):
    manager.dispatch("update", guid, u"Updating Git repository")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("git"), args=["fetch"], env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted updating: Couldn't fetch from github")
    out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("git"), args=["reset", "--hard", "origin/master"], env=os.environ)
    if code != 0:
        manager.log(out)
        manager.log(err)
        raise manager.exception(u"Aborted updating: Couldn't reset to origin/master")

    # Delete compiled files so that we can delete commands
    yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("find"), args=[".", "-type", "f", "-name", "*.pyc", "-delete"], env=os.environ)

    # Reload everything but IRC so the bot doesn't flicker
    # Also don't reload crunchy because log spam
    manager.dispatch("update", guid, u"Reloading modules")
    yield manager.master.loadModules(["irc", "crunchy"], True)
