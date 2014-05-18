from twisted.internet.defer import returnValue
from datetime import datetime as dt

config = {
    "access": "admin",
    "help": ".profile [command] || .profile release || How many times a command has been used and it's average time spent running."
}

def command(guid, manager, irc, channel, user, command):
    name = "command_{}".format(command.encode("utf8"))
    manager.dispatch("update", guid, u"Waiting on profiler.stats")
    stats = yield manager.master.modules["profiler"].stats()
    data = stats.get(name, {"calls": 0, "time": 0})
    avg = data["time"] / data["calls"] if data["calls"] else 0.0
    irc.msg(channel, u"{} has been called {:,d} times with an average length of {:,.6f} seconds".format(command, data["calls"], avg))
