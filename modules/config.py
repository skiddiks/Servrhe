# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
import json

dependencies = ["db"]

class Shard(object):
    def __init__(self, master, name):
        self.master = master
        self.name = name

    def get(self, key, default=None):
        return self.master.modules["config"].get(self.name, key, default)

    def set(self, key, value):
        return self.master.modules["config"].set(self.name, key, value)

class Module(object):
    def __init__(self, master):
        self.master = master

    def stop(self):
        pass

    @inlineCallbacks
    def get(self, namespace, key, default=None):
        result = yield self.master.modules["db"].configGet(namespace, key)
        returnValue(json.loads(result) or default)

    @inlineCallbacks
    def set(self, namespace, key, value):
        try:
            result = yield self.master.modules["db"].configSet(namespace, key, json.dumps(value, separators=(',', ':')))
        except:
            self.err("Failed to save {}:{} = {!r}", namespace, key, value)
            returnValue(False)
        else:
            returnValue(True)

    def interface(self, name):
        return Shard(self.master, name)
