from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.internet.protocol import Protocol, Factory

from datetime import datetime as dt
import json

dependencies = []

class Module(object):
    def __init__(self, master):
        self.master = master
        self.factory = ProgressFactory(master)
        self.reports = {}
        self.report_cleaner = LoopingCall(self.clean)
        self.report_cleaner.start(60)

    def stop(self):
        if self.report_cleaner is not None and self.report_cleaner.running:
            self.report_cleaner.stop()
            self.report_cleaner = None

    def clean(self):
        for k, v in self.reports.items():
            if (dt.utcnow() - v["updated"]).total_seconds() >= 30*60:
                del self.reports[k]
                self.factory.broadcast({"type": "remove", "key": v["script"]})

    def report(self, ip, script, completed, total):
        self.reports[ip + script] = {
            "ip": ip,
            "script": script,
            "completed": completed,
            "total": total,
            "updated": dt.utcnow()
        }
        self.factory.broadcast({"type": "update", "key": script, "values": {
            "script": script,
            "completed": completed,
            "total": total
        }})

class ProgressProtocol(Protocol):
    def connectionMade(self):
        values = {}
        for o in sorted(self.factory.master.modules["progress"].reports.values(), key=lambda x: x["updated"], reverse=True):
            if o["script"] not in values:
                values[o["script"]] = {
                    "script": o["script"],
                    "completed": o["completed"],
                    "total": o["total"]
                }
        self.transport.write(json.dumps({
            "type": "initial",
            "values": values.values()
        }))
        self.factory.protocols.add(self)

    def connectionLost(self, reason):
        self.factory.protocols.remove(self)

class ProgressFactory(Factory):
    protocol = ProgressProtocol

    def __init__(self, master):
        self.master = master
        self.protocols = set()

    def broadcast(self, o):
        m = json.dumps(o)
        for p in self.protocols:
            p.transport.write(m)
