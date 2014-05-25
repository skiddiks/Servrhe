# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
import re

dependencies = ["db"]

class Module(object):
    def __init__(self, master):
        self.master = master

    def stop(self):
        pass

    @inlineCallbacks
    def resolve(self, name):
        result = yield self.master.modules["db"].alias2userName(name)

        if result is None:
            yield self.master.modules["db"].createUser(name)
            result = name

        returnValue(result)

    @inlineCallbacks
    def learn(self, master, slave):
        if re.match("guest\d+", master.lower()) or re.match("guest\d+", slave.lower()):
            return

        uid1 = yield self.master.modules["db"].alias2userId(master)
        uid2 = yield self.master.modules["db"].alias2userId(slave)

        if uid1 and uid2:
            # If both exist, either they are already linked, or two alias groups exist
            # We don't merge alias groups since it is abusable
            return
        elif uid1:
            # If only the "master" exists, add the "slave" as an alias
            yield self.master.modules["db"].createAlias(uid1, slave)
        elif uid2:
            # If only the "slave" exists, add the "master" as an alias
            yield self.master.modules["db"].createAlias(uid2, master)
        else:
            # If neither exist, create a new alias group with "master" as the name
            user_id = yield self.master.modules["db"].createUser(master)
            yield self.master.modules["db"].createAlias(user_id, slave)

    def irc_rename(self, old, new):
        self.learn(old, new)
