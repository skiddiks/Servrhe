# -*- coding: utf-8 -*-

from datetime import datetime as dt

dependencies = []

class Module(object):
    def __init__(self, master):
        self.master = master
        self.running = {}

    def stop(self):
        pass

    def commands_start(self, process, name, guid, channel, user, args, kwargs):
        self.running[guid] = {
            "guid": guid,
            "process": process,
            "command": u" ".join([u".{}".format(name)] + [u"\"{}\"".format(x) for x in args] + [u"--{}=\"{}\"".format(k,v) for k,v in kwargs.items()]),
            "user": user,
            "channel": channel,
            "started": dt.utcnow(),
            "updated": dt.utcnow(),
            "status": u"Running",
            "substatus": None
        }

    def commands_update(self, guid, status):
        if guid not in self.running:
            return
        self.running[guid]["status"] = status
        self.running[guid]["substatus"] = None
        self.running[guid]["updated"] = dt.utcnow()
        self.log("{!r}", self.running[guid])

    def commands_progress(self, guid, substatus):
        if guid not in self.running:
            return
        self.running[guid]["substatus"] = u" ({})".format(substatus)
        self.running[guid]["updated"] = dt.utcnow()
        self.log(self.format(self.running[guid]))

    def commands_finish(self, guid):
        if guid not in self.running:
            return
        del self.running[guid]

    def format(self, o):
        return u"[{}] `{}` by {} on {} is {}{}".format(o["guid"][0:6], o["command"], o["user"], o["channel"], o["status"], o["substatus"] if o["substatus"] else u"")

    def list(self):
        return [self.format(o) for o in self.running.values()]

    def cancel(self, guid):
        processes = [p for p in self.running.values() if p["guid"].startswith(guid)]
        if len(processes) == 1:
            processes[0]["process"].cancel()
            return u"Cancelled {}".format(processes[0]["guid"])
        elif not processes:
            return u"No processes matched GUID: {}".format(guid)
        else:
            return u"GUID wasn't specific enough. Found: {}".format(u", ".join([p["guid"] for p in processes.values()]))
