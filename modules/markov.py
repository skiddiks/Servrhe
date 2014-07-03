# -*- coding: utf-8 -*-

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.task import LoopingCall
from collections import deque, Counter
import datetime, json, inspect, random, re

dependencies = ["config", "alias"]

def normalize(word):
  if word is None:
    return None
  return re.sub(r'[^a-z0-9-]', '', word.lower().strip())

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("markov")
        self.ranking = {}
        self.rankingLoop = LoopingCall(self.loadRanking)
        self.rankingLoop.start(60)

    def stop(self):
        if self.rankingLoop is not None and self.rankingLoop.running:
            self.rankingLoop.stop()
            self.rankingLoop = None

    @inlineCallbacks
    def loadRanking(self):
        result = yield self.master.modules["db"].markovRankings()
        self.ranking = {}
        for rank, data in enumerate(result):
            self.ranking[data["name"].lower()] = {
                "rank": rank+1,
                "name": data["name"],
                "words": data["words"]
            }
    
    @inlineCallbacks
    def learn(self, name, phrase, channel):
        name = yield self.master.modules["alias"].resolve(name)
        uid = yield self.master.modules["db"].userLookup(name)
        cid = yield self.master.modules["db"].channelLookup(channel)

        words = [w.encode("UTF-8") for w in phrase.split(" ")]
        c1 = [None] + words[:-1]
        c2 = words[:]
        c3 = words[1:] + [None]
        chain = zip(c1, c2, c3)

        rows = [[uid, cid, w1, w2, w3, normalize(w1), normalize(w2), normalize(w3)] for w1, w2, w3 in chain]

        yield self.master.modules["db"].markovLearn(rows)

    @inlineCallbacks
    def ramble(self, name=None, seed=None, entropy=False):
        if name:
            name = yield self.master.modules["alias"].resolve(name)
            if name not in self.ranking:
                returnValue("")

        message = deque()

        if seed:
            before, _, after = yield self.find(name, word2=seed)
            before = None if before is False else before
            after = None if after is False else after
            if before is not None or after is not None:
                message.append(before)
                message.append(seed)
                message.append(after)
                while message[0] is not None and len(message) < 80:
                    if entropy:
                        word = None
                    else:
                        word, _, _ = yield self.find(name, word2=message[0], word3=message[1])
                    if word is None:
                        word, _, _ = yield self.find(name, word2=message[0])
                    message.appendleft(word)
            else:
                words = yield self.find(name, word1=None)
                message.extend(words)
        else:
            words = yield self.find(name, word1=None)
            message.extend(words)

        while message[-1] is not None and len(message) < 80:
            if entropy:
                word = None
            else:
                _, _, word = yield self.find(name, word1=message[-2], word2=message[-1])
            if word is None:
                _, _, word = yield self.find(name, word2=message[-1])
            message.append(word)

        message = list(message)
        response = u" ".join(message[1:-1])
        if len(response) > 320:
            response = response[:320] + u"..."
        returnValue(response)

    @inlineCallbacks
    def find(self, name, word1=None, word2=None, word3=None):
        if not word2:
            return [None, None, None]

        if word1:
            result = yield self.master.modules["db"].markovForward(name, normalized(word2), normalized(word3))
        elif word3:
            result = yield self.master.modules["db"].markovBackward(name, normalized(word1), normalized(word2))
        else:
            result = yield self.master.modules["db"].markovMiddle(name, normalized(word2))

        returnValue(result)

    @inlineCallbacks
    def count(self, word):
        result = yield self.db.find({"word2": word}, fields=["name"])
        returnValue(Counter([row["name"] for row in result]))

    @inlineCallbacks
    def irc_message(self, channel, user, message):
        for name, method in inspect.getmembers(self, predicate=inspect.ismethod):
            if name.startswith("filter_"):
                result = yield maybeDeferred(method, message, user, channel)
                if not result:
                    return
        self.learn(user, message, channel)

    def filter_commands(self, message, user, channel):
        return not (message.startswith(".") or message.startswith("@") or message.startswith("!"))

    def filter_links(self, message, user, channel):
        return "http" not in message and "ftp" not in message

    @inlineCallbacks
    def filter_banwords(self, message, user, channel):
        banwords = yield self.config.get("banwords")
        for word in banwords:
            if word in message:
                returnValue(False)
        returnValue(True)

    @inlineCallbacks
    def filter_banusers(self, message, user, channel):
        banusers = yield self.config.get("banusers")
        returnValue(user not in banusers)

    def filter_quotes(self, message, user, channel):
        match1 = re.match("\[Quote\] #\d+ added by .* ago.", message)
        match2 = re.match("\[Quote\] \d+ matches found: #[\d,]+", message)
        return not (user == "Quotes" and (match1 or match2))
