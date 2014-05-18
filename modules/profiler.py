# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue

dependencies = ["config"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("profiler")
        self.running = {}

    def stop(self):
        pass

    def stats(self):
        return self.config.get("stats", {})

    def commands_start(self, name, guid, *args):
        self.running[guid] = {"name": "command_{}".format(name), "start": reactor.seconds()}

    @inlineCallbacks
    def commands_finish(self, guid):
        if guid not in self.running:
            return
        data = self.running[guid]
        name, start = data["name"], data["start"]
        length = reactor.seconds() - start
        del self.running[guid]
        stats = yield self.stats()
        if name not in stats:
            stats[name] = {"time": 0, "calls": 0}
        stats[name]["calls"] += 1
        stats[name]["time"] += length
        self.dispatch("update", name, stats[name]["time"], stats[name]["calls"])
        self.config.set("stats", stats)
