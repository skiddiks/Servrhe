# -*- coding: utf-8 -*-

from collections import namedtuple
from bs4 import UnicodeDammit
from random import choice
from twisted.application import internet
from twisted.internet import protocol
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.words.protocols.irc import IRCClient

dependencies = ["config", "db"]

def normalize(s):
    if isinstance(s, unicode):
        return s

    try:
        u = s.decode("utf8")
    except:
        try:
            u = (s[:-1]).decode("utf8")
        except:
            try:
                u = UnicodeDammit.detwingle(s).decode("utf8")
            except:
                u = UnicodeDammit(s, ["utf8", "windows-1252"]).unicode_markup

    return u

class IRC(protocol.ReconnectingClientFactory):
    maxDelay = 5 * 60

    def __init__(self, master):
        self.master = master
        master.irc = self
        self.connection = None

    def buildProtocol(self, addr):
        p = self.master.modules["irc"]
        if p.connected:
            return
        p.factory = self
        return p

class Module(IRCClient):
    """
    Handles the IRC interface for the bot.

    PROPERTIES
    ranks - standardizes the ranking of users in channels
    channels - contains all channels the bot is in, as well as the users and their rank

    EVENTS
    connected - Bot connected to server
    disconnected - Bot disconnected from server
    joined - Bot joined a channel
    left - Bot left a channel
    kicked - Bot was kicked from a channel
    sent_message - Bot sent a message
    sent_notice - Bot sent a notice

    join - User joined a channel
    part - User left a channel
    kick - User was kicked from a channel
    message - Either channel or private message
    notice - Any notices sent to the bot
    action - A user used /me
    rename - A user changed their nick
    mode - A user's mode changed

    topic - A channel's topic changed
    motd - The server's MOTD
    """
    connected = False
    factory = None
    lineRate = 0.400
    nick_check = None
    performLogin = 0
    ranks = namedtuple("Rank",["DEFAULT","VOICE","HOP","OP","ADMIN","OWNER"])._make(range(6))
    sourceURL = "https://github.com/Fugiman/Servrhe"
    versionEnv = "Twisted-Python"
    versionName = "Servrhe (Custom Bot)"
    versionNum = "5.0"

    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("irc")

        irc = IRC(master)
        internet.TCPClient(master.options["irchost"], master.options["ircport"], irc).setServiceParent(master)

    def stop(self):
        if self.connected:
            self.transport.loseConnection()
        if self.factory:
            self.factory.stopTrying()

    # Connection Handling
    @inlineCallbacks
    def connectionMade(self):
        self.connected = True
        IRCClient.connectionMade(self)
        nick = yield self.config.get("nick", "ServrheV5")
        self.register(nick.encode("utf8"))
        self.dispatch("connected")

    @inlineCallbacks
    def signedOn(self):
        password = yield self.config.get("pass")
        if password:
            IRCClient.msg(self, "NickServ","IDENTIFY {}".format(password.encode("utf8")))
        self.factory.resetDelay()
        self.factory.connection = self
        self.nick_check = LoopingCall(self.nickCheck)
        self.nick_check.start(60)
        self.channels = {}
        channels = yield self.master.modules["db"].channelList()
        for c, p in channels.items():
            self.join(u"{} {}".format(c, p) if p else c, True)
    
    def connectionLost(self, reason=None):
        self.connected = False
        self.factory.connection = None
        self.channels = {}
        if self.nick_check:
            self.nick_check.stop()
            self.nick_check = None
        self.dispatch("disconnected")

    # Force nick to be that of the config
    @inlineCallbacks
    def nickCheck(self):
        nick = yield self.config.get("nick")
        if nick and nick != self.nickname:
            self.setNick(nick.encode("utf8"))

    # Bubble message handling
    def privmsg(self, hostmask, channel, message):
        user = hostmask.split("!", 1)[0]
        channel = channel if channel != self.nickname else user

        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("message", channel, user, message)

    def noticed(self, hostmask, channel, message):
        user = hostmask.split("!", 1)[0]
        channel = channel if channel != self.nickname else user

        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("notice", channel, user, message)

    def kickedFrom(self, channel, kicker, message):
        kicker = normalize(kicker)
        channel = normalize(channel)
        message = normalize(message)

        if channel not in self.channels:
            return

        del self.channels[channel]
        self.config.set("channels", self.channels.keys())
        self.dispatch("kicked", channel, kicker, message)

    def action(self, user, channel, message):
        user = normalize(user)
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("action", channel, user, message)

    def topicUpdated(self, user, channel, message):
        channel = normalize(channel)
        message = normalize(message)

        self.dispatch("topic", channel, message)

    def receivedMOTD(self, motd):
        motd = "".join([l.rstrip() for l in motd])
        motd = normalize(motd)

        self.dispatch("motd", motd)

    # Convience methods
    def _reallySendLine(self, line):
        if line.startswith("PRIVMSG") and not line.startswith("PRIVMSG NickServ"):
            # FUCK YOU ELITE_SOBA AND ARNAVION
            prefix, seperator, text = line.partition(":")
            fuckyou = choice([u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u"\u200B", u".kb Elite_Soba ", u".kb Arnavion "])
            line = (u"{}{}{}{}".format(prefix, seperator, fuckyou, text.decode("utf8"))).encode("utf8")
        IRCClient._reallySendLine(self, line)

    def msg(self, channel, message):
        IRCClient.msg(self, channel.encode("utf8"), message.encode("utf8")) # _reallySendLine handles this for us
        nick = normalize(self.nickname)
        self.dispatch("sent_message", channel, nick, message)

    def notice(self, user, message):
        IRCClient.notice(self, user.encode("utf8"), (u"\u200B" + message).encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("sent_notice", user, nick, message)

    def kickban(self, channel, user, reason=None):
        if not reason:
            reason = user
        self.mode(channel.encode("utf8"), True, "b", mask="{}!*@*".format(user.encode("utf8")))
        self.kick(channel.encode("utf8"), user.encode("utf8"), reason.encode("utf8"))

    @inlineCallbacks
    def join(self, channel, no_database=False):
        actual, _, password = channel.partition(" ")

        if not no_database:
            c, p, ac = yield self.master.modules["db"].channelGet(actual)

            if c:
                actual = c

            if not password and p:
                password = p

            yield self.master.modules["db"].channelSet(actual, password, True)

        if password:
            channel = u"{} {}".format(actual, password)

        self.channels[actual] = {}

        IRCClient.join(self, channel.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("joined", actual, nick)

    @inlineCallbacks
    def leave(self, channel):
        if channel not in self.channels:
            return
        del self.channels[channel]
        IRCClient.leave(self, channel.encode("utf8"))
        nick = normalize(self.nickname)
        self.dispatch("left", channel, nick)
        c, p, ac = yield self.master.modules["db"].channelGet(channel)
        yield self.master.modules["db"].channelSet(c, p, False)

    # Channel tracking
    def userJoined(self, user, channel):
        user = normalize(user)
        channel = normalize(channel)
        self.channels[channel][user] = self.ranks.DEFAULT
        self.dispatch("join", channel, user)

    def userLeft(self, user, channel):
        user = normalize(user)
        channel = normalize(channel)
        del self.channels[channel][user]
        self.dispatch("part", channel, user)

    def userQuit(self, user, message):
        user = normalize(user)
        for name, channel in self.channels.items():
            if user in channel:
                del channel[user]
                self.dispatch("part", name, user)

    def userKicked(self, user, channel, kicker, message):
        user = normalize(user)
        channel = normalize(channel)
        kicker = normalize(kicker)
        message = normalize(message)
        del self.channels[channel][user]
        self.dispatch("kick", channel, user, kicker, message)

    def userRenamed(self, old, new):
        old = normalize(old)
        new = normalize(new)
        for channel in self.channels.values():
            if old in channel:
                channel[new] = channel[old]
                del channel[old]
        self.dispatch("rename", old, new)

    def irc_RPL_NAMREPLY(self, prefix, params):
        _, _, channel, users = params
        channel = normalize(channel)
        users = users.split(" ")
        ranks = {
            "~": self.ranks.OWNER,
            "&": self.ranks.ADMIN,
            "@": self.ranks.OP,
            "%": self.ranks.HOP,
            "+": self.ranks.VOICE,
            "": self.ranks.DEFAULT
        }
        for user in users:
            rank, name = user[0], user[1:]
            if rank not in "~&@%+":
                rank, name = "", user
            name = normalize(name)
            self.channels[channel][name] = ranks[rank]
            self.dispatch("mode", channel, name, self.channels[channel][name])

    def modeChanged(self, user, channel, added, modes, args):
        channel = normalize(channel)
        if not channel.startswith("#"):
            return

        ranks = {
            "q": self.ranks.OWNER,
            "a": self.ranks.ADMIN,
            "o": self.ranks.OP,
            "h": self.ranks.HOP,
            "v": self.ranks.VOICE
        }
        for mode, name in zip(modes, args):
            if mode not in ranks:
                continue
            name = normalize(name)
            rank = ranks[mode]
            currank = self.channels[channel][name]
            if added and rank > currank:
                self.channels[channel][name] = rank
            if not added and rank == currank:
                self.channels[channel][name] = self.ranks.DEFAULT
            if self.channels[channel][name] != currank:
                self.dispatch("mode", channel, name, self.channels[channel][name])
