# -*- coding: utf-8 -*-
dependencies = []
class Module(object):
    def __init__(self, master):
        pass
    def stop(self):
        pass

"""
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.task import LoopingCall
from collections import namedtuple
from datetime import datetime as dt
import json, urllib

dependencies = ["config", "commands", "utils", "irc"]

StaffObject = namedtuple("StaffObject", ["id", "rank", "name", "position", "description", "quote"])

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("staff")
        self.ranks = ("Retired", "Party Congress", "Central Committee")
        self.shows = {}
        self.staff_loop = LoopingCall(self.refreshStaff)
        self.staff_loop.start(180)

    def stop(self):
        if self.staff_loop is not None and self.staff_loop.running:
            self.staff_loop.stop()
            self.staff_loop = None

    @inlineCallbacks
    def load(self, *params, **kwargs):
        exception = self.master.modules["commands"].exception
        base = yield self.config.get("endpoint")
        url = "/".join([base.encode("utf-8")] + [unicode(x).encode("utf-8") for x in params])
        url = urllib.quote(url,"/:")
        headers = {}
        data = ""
        if "data" in kwargs:
            d = kwargs["data"]
            d["key"] = yield self.config.get("key")
            data = json.dumps(d)
            headers["Content-Type"] = ["application/json"]
        body = yield self.master.modules["utils"].fetchPage(url, data, headers)
        data = json.loads(body)
        if "status" in data and not data["status"]:
            raise exception(u"Error in staff API call: {}".format(data["message"]))
        returnValue(data["results"])

    @inlineCallbacks
    def refreshStaff(self):
        data = yield self.load("members")
        self.staff = {}
        for member in data:
            self.staff[member["id"]] = StaffObject(member["id"], self.ranks[member["rank"]], member["name"], member["position"], member["description"], member["quote"])

    def resolve(self, name):
        exception = self.master.modules["commands"].exception
        matches = []
        if not name:
            raise exception(u"Staff name not specified.")
        name = name.lower()
        for s in self.staff.values():
            if s.name.lower() == name:
                return s
            if s.name.lower().count(name):
                matches.append(s)
        if len(matches) > 1:
            r = [s.name for s in matches]
            if len(r) > 5:
                extra = "and {:d} more.".format(len(r) - 5)
                r = r[:5] + [extra]
            raise exception(u"Staff name not specific, found: {}".format(u", ".join(r)))
        elif not matches:
            raise exception(u"Staff name not found.")
        return matches[0]

    @inlineCallbacks
    def hire(self, name, position):
        data = {
            "data": {
                "name": name,
                "tier": 1,
                "position": position,
                "description": "",
                "quote": ""
            }
        }
        yield self.load("new", data=data)

    @inlineCallbacks
    def fire(self, member):
        data = {
            "method": "",
            "data": {
                "name": name,
                "tier": 1,
                "position": position,
                "description": "",
                "quote": ""
            }
        }
        yield self.load("new", data=data)
"""