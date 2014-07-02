# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
import re

dependencies = []

QUERIES = {
    "create_user": lambda f, name: f('INSERT INTO `users` (`name`) VALUES (%s)', (name, )),
    "create_alias": lambda f, uid, name: f('INSERT INTO `aliases` (`user_id`, `name`) VALUES (%s, %s)', (uid, name)),
    "config_get": lambda f, n, k: f('SELECT `value` FROM `config` WHERE `namespace` = %s AND `key` = %s', (n, k)),
    "config_set": lambda f, n, k, v: f('INSERT INTO `config` (`namespace`, `key`, `value`) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE `value` = %s', (n, k, v, v)),
    "alias_to_user_id": lambda f, name: f('SELECT `user_id` FROM `aliases` WHERE `name` = %s', (name, )),
    "alias_to_user_name": lambda f, name: f('SELECT `users`.`name` FROM `users` INNER JOIN `aliases` ON `users`.`id` = `aliases`.`user_id` WHERE `aliases`.`name` = %s', (name, )),
    "alias_to_permissions": lambda f, name: f('SELECT `permissions`.`name` FROM `permissions` INNER JOIN `user_permissions` ON `permissions`.`id` = `user_permissions`.`permission_id` INNER JOIN `aliases` ON `user_permissions`.`user_id` = `aliases`.`user_id` WHERE `aliases`.`name` = %s', (name, )),
    "alias_to_number": lambda f, name: f('SELECT `numbers`.`number` FROM `numbers` INNER JOIN `aliases` ON `numbers`.`user_id` = `aliases`.`user_id` WHERE `aliases`.`name` = %s', (name, )),
    "number_to_user_name": lambda f, number: f('SELECT `users`.`name` FROM `users` INNER JOIN `numbers` ON `users`.`id` = `numbers`.`user_id` WHERE `numbers`.`number` = %s', (number, )),
    "number_list": lambda f: f('SELECT `users`.`name`, `numbers`.`number` FROM `numbers` INNER JOIN `users` ON `numbers`.`user_id` = `users`.`id`'),
    "channel_list": lambda f: f('SELECT `name`, `password` FROM `channels` WHERE `autoconnect` = 1'),
    "channel_get": lambda f, channel: f('SELECT `name`, `password`, `autoconnect` FROM `channels` WHERE `name` = %s', (channel, )),
    "channel_set": lambda f, c, p, ac: f('INSERT INTO `channels` (`name`, `password`, `autoconnect`) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE `password` = %s, `autoconnect` = %s', (c, p, ac, p, ac)),
    "permission_get": lambda f, name: f('SELECT `id` FROM `permissions` WHERE `name` = %s', (name, )),
    "permission_grant": lambda f, uid, pid: f('INSERT INTO `user_permissions` (`user_id`, `permission_id`) VALUES (%s, %s)', (uid, pid))
}

def createUser(cursor, name):
    QUERIES["create_user"](cursor.execute, name)
    user_id = cursor.lastrowid
    QUERIES["create_alias"](cursor.execute, user_id, name)
    return user_id

def grantPermission(cursor, name, permission):
    QUERIES["alias_to_user_id"](cursor.execute, name)
    result = cursor.fetchone()
    if not result:
        return False
    uid = result[0]

    QUERIES["permission_get"](cursor.execute, permission)
    result = cursor.fetchone()
    if not result:
        return False
    pid = result[0]

    QUERIES["permission_grant"](cursor.execute, uid, pid)
    return True

class Module(object):
    def __init__(self, master):
        self.master = master

    def stop(self):
        pass

    def createUser(self, name):
        return self.master.db.runInteraction(createUser, name)

    def createAlias(self, uid, name):
        return QUERIES["create_alias"](self.master.db.runOperation, uid, name)

    @inlineCallbacks
    def alias2userId(self, name):
        result = yield QUERIES["alias_to_user_id"](self.master.db.runQuery, name)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def alias2userName(self, name):
        result = yield QUERIES["alias_to_user_name"](self.master.db.runQuery, name)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def alias2permissions(self, name):
        results = yield QUERIES["alias_to_permissions"](self.master.db.runQuery, name)
        returnValue([r[0] for r in results])

    @inlineCallbacks
    def configGet(self, namespace, key):
        result = yield QUERIES["config_get"](self.master.db.runQuery, namespace, key)
        returnValue(result[0][0] if result else None)

    def configSet(self, namespace, key, value):
        return QUERIES["config_set"](self.master.db.runOperation, namespace, key, value)

    @inlineCallbacks
    def alias2number(self, name):
        result = yield QUERIES["alias_to_number"](self.master.db.runQuery, name)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def number2userName(self, number):
        result = yield QUERIES["number_to_user_name"](self.master.db.runQuery, number)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def numberList(self):
        results = yield QUERIES["number_list"](self.master.db.runQuery)
        returnValue({r[0]: r[1] for r in results})

    @inlineCallbacks
    def channelList(self):
        results = yield QUERIES["channel_list"](self.master.db.runQuery)
        returnValue({r[0]: r[1] for r in results})

    @inlineCallbacks
    def channelGet(self, channel):
        result = yield QUERIES["channel_get"](self.master.db.runQuery, channel)
        returnValue((result[0][0], result[0][1], bool(result[0][2])) if result else (None, None, None))

    def channelSet(self, channel, password, auto_connect):
        return QUERIES["channel_set"](self.master.db.runOperation, channel, password, int(auto_connect))

    def grantPermission(self, name, permission):
        return self.master.db.runInteraction(grantPermission, name, permission)
