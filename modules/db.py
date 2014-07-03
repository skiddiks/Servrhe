# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
import re, functools

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
    "permission_grant": lambda f, uid, pid: f('INSERT INTO `user_permissions` (`user_id`, `permission_id`) VALUES (%s, %s)', (uid, pid)),
    "user_lookup": lambda f, name: f('SELECT `id` FROM `users` WHERE `users`.`name` = %s', (name, )),
    "channel_lookup": lambda f, name: f('SELECT `id` FROM `channels` WHERE `channels`.`name` = %s', (name, )),
    "markov_rankings": lambda f: f('SELECT `users`.`name`, COUNT(`markov`.`id`) FROM `markov` INNER JOIN `users` ON `markov`.`user_id` = `users`.`id` GROUP BY `users`.`name` ORDER BY COUNT(`markov`.`id`) DESC'),
    "markov_learn": lambda f, r: f('INSERT INTO `markov` (`user_id`, `channel_id`, `word1`, `word2`, `word3`, `normalized1`, `normalized2`, `normalized3`) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)', r),
    "markov_initial": lambda f: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized1` IS NULL ORDER BY RAND() LIMIT 1'),
    "markov_initial_named": lambda f, n: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized1` IS NULL AND `user_id` = %s ORDER BY RAND() LIMIT 1', (n, )),
    "markov_forward": lambda f, w1, w2: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized1` = %s AND `normalized2` = %s ORDER BY RAND() LIMIT 1', (w1, w2)),
    "markov_forward_named": lambda f, w1, w2, n: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized1` = %s AND `normalized2` = %s AND `user_id` = %s ORDER BY RAND() LIMIT 1', (w1, w2, n)),
    "markov_middle": lambda f, w2: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized2` = %s ORDER BY RAND() LIMIT 1', (w2, )),
    "markov_middle_named": lambda f, w2, n: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized2` = %s AND `user_id` = %s ORDER BY RAND() LIMIT 1', (w2, n)),
    "markov_backward": lambda f, w2, w3: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized2` = %s AND `normalized3` = %s ORDER BY RAND() LIMIT 1', (w2, w3)),
    "markov_backward_named": lambda f, w2, w3, n: f('SELECT `word1`, `word2`, `word3` FROM `markov` WHERE `normalized2` = %s AND `normalized3` = %s AND `user_id` = %s ORDER BY RAND() LIMIT 1', (w2, w3, n))
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

def markovLearn(cursor, rows):
    QUERIES["markov_learn"](cursor.executemany, rows)

class Module(object):
    def __init__(self, master):
        self.master = master

    def logAndRun(self, query, args=None):
        self.log(u"{}", query % args if args else query)
        return self.master.db.runQuery(query, args)

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

    @inlineCallbacks
    def userLookup(self, name):
        result = yield QUERIES["user_lookup"](self.master.db.runQuery, name)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def channelLookup(self, name):
        result = yield QUERIES["channel_lookup"](self.master.db.runQuery, name)
        returnValue(result[0][0] if result else None)

    @inlineCallbacks
    def markovRankings(self):
        results = yield QUERIES["markov_rankings"](self.master.db.runQuery)
        returnValue([{"name": r[0], "words": r[1]} for r in results])

    def markovLearn(self, rows):
        return self.master.db.runInteraction(markovLearn, rows)

    @inlineCallbacks
    def markovInitial(self, name):
        if name:
            name = yield self.alias2userId(name)
            results = yield QUERIES["markov_initial_named"](self.logAndRun, name)
        else:
            results = yield QUERIES["markov_initial"](self.logAndRun)
        returnValue(results[0] if results else [None, None, None])

    @inlineCallbacks
    def markovForward(self, name, w1, w2):
        if name:
            name = yield self.alias2userId(name)
            results = yield QUERIES["markov_forward_named"](self.logAndRun, w1, w2, name)
        else:
            results = yield QUERIES["markov_forward"](self.logAndRun, w1, w2)
        returnValue(results[0] if results else [None, None, None])

    @inlineCallbacks
    def markovMiddle(self, name, w2):
        if name:
            name = yield self.alias2userId(name)
            results = yield QUERIES["markov_middle_named"](self.logAndRun, w2, name)
        else:
            results = yield QUERIES["markov_middle"](self.logAndRun, w2)
        returnValue(results[0] if results else [None, None, None])

    @inlineCallbacks
    def markovBackward(self, name, w2, w3):
        if name:
            name = yield self.alias2userId(name)
            results = yield QUERIES["markov_backward_named"](self.logAndRun, w2, w3, name)
        else:
            results = yield QUERIES["markov_backward"](self.logAndRun, w2, w3)
        returnValue(results[0] if results else [None, None, None])
