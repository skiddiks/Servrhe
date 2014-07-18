# -*- coding: utf-8 -*-

from twisted.application import service, strports
from twisted.enterprise import adbapi
from twisted.internet import defer, reactor
from twisted.plugin import IPlugin
from twisted.python import log, usage
from twisted.web import client, server, resource
from zope.interface import implements
import copy, functools, inspect, pkgutil, sys, txmongo

class Options(usage.Options):
    optParameters = [
        ["irchost", "ih", "irc.rizon.net", "The IRC server hostname"],
        ["ircport", "ip", 6667, "The IRC server port", int],
        ["web", "w", "tcp:8091", "The webserver endpoint"],
        ["moddir", "m", "modules", "The module directory"]
    ]


class Master(service.MultiService):
    def __init__(self, options):
        service.MultiService.__init__(self)
        self.moddir = options["moddir"]
        self.options = options
        self.db = None
        self.modules = {}

    def privilegedStartService(self):
        pass

    @defer.inlineCallbacks
    def startService(self):
        self.agent = client.Agent(reactor, connectTimeout=5)
        self.agent._pool._factory.noisy = False
        self.db = adbapi.ConnectionPool("MySQLdb", db="servrhe", cp_reconnect=True)
        yield self.loadModules()
        service.MultiService.startService(self)

    @defer.inlineCallbacks
    def loadModules(self, filter=[], blacklist=False):
        modules = {}
        pending = []

        # Preserve some old modules if desired
        if filter:
            for name, module in self.modules.items():
                if (name not in filter and not blacklist) or (name in filter and blacklist):
                    modules[name] = module
                    del self.modules[name]

        # Kill old modules
        deferreds = []
        for module in self.modules.values():
            deferreds.append(defer.maybeDeferred(module.stop))
        yield defer.DeferredList(deferreds)

        # Copy over preserved modules
        self.modules = modules

        # Find new modules
        for loader, name, ispkg in pkgutil.iter_modules([self.moddir]):
            if ispkg or name in modules or (filter and not blacklist and name not in filter):
                continue
            try:
                module = getattr(__import__(self.moddir, fromlist=[name]), name)
                reload(module)
                pending.append((name, module))
            except:
                self.err("Failed to import {}.{}", self.moddir, name)

        # Load new modules in order
        while pending:
            remaining = len(pending)
            for name, module in pending:
                loadable = True
                for dependency in module.dependencies:
                    if dependency not in modules:
                        loadable = False
                        break
                if not loadable:
                    continue
                self.modules[name] = module.Module(self)
                self.modules[name].name = name.capitalize()
                self.modules[name].dependencies = module.dependencies
                self.modules[name].log = functools.partial(self.log, cls=name.capitalize())
                self.modules[name].err = functools.partial(self.err, cls=name.capitalize())
                self.modules[name].dispatch = functools.partial(self.dispatch, name)
                pending.remove((name, module))
            if remaining == len(pending):
                unloaded = ", ".join([x[0] for x in pending])
                self.err("Dependency error occured. Failed to load: {}", unloaded)
                break
        self.log("Loaded modules: {}", ", ".join(sorted(self.modules.keys())))

    def log(self, message, *args, **kwargs):
        cls = kwargs["cls"] if "cls" in kwargs else "Master"
        func = kwargs["func"] if "func" in kwargs else inspect.stack()[1][3]
        log.msg(message.format(*args).encode("utf8"), system="{}.{}".format(cls, func))

    def err(self, message=None, *args, **kwargs):
        err = kwargs["error"] if "error" in kwargs else None
        cls = kwargs["cls"] if "cls" in kwargs else "Master"
        func = kwargs["func"] if "func" in kwargs else inspect.stack()[1][3]
        log.err(err, message.format(*args).encode("utf8"), system="{}.{}".format(cls, func))

    def dispatch(self, cls, name, *args):
        for module in self.modules.values():
            method = getattr(module, "{}_{}".format(cls, name), None)
            if callable(method):
                try:
                    method(*args)
                except:
                    self.err("Failure calling {}.{}_{}", module.name, cls, name)

    @defer.inlineCallbacks
    def stopService(self):
        yield service.MultiService.stopService(self)
        deferreds = []
        for module in self.modules.values():
            deferreds.append(defer.maybeDeferred(module.stop))
        yield defer.DeferredList(deferreds)
        self.db.close()
        self.modules = {}
        self.db = None

class Web(server.Site):
    def __init__(self, master):
        self.master = master
        master.web = self
        server.Site.__init__(self, resource.ErrorPage(500, "Internal Server Error", "Web module failed to load"))

    def getChildWithDefault(self, pathEl, request):
        request.site = self
        _resource = self.master.modules["web"] if "web" in self.master.modules else self.resource
        return _resource.getChildWithDefault(pathEl, request)

    def getResourceFor(self, request):
        request.site = self
        request.sitepath = copy.copy(request.prepath)
        _resource = self.master.modules["web"] if "web" in self.master.modules else self.resource
        return resource.getChildForRequest(_resource, request)

class ServiceMaker(object):
    implements(service.IServiceMaker, IPlugin)
    tapname = "servrhe"
    description = "A highly modular IRC bot with a web interface"
    options = Options

    def makeService(self, options):
        master = Master(options)

        web = Web(master)
        strports.service(options["web"], web).setServiceParent(master)

        return master

serviceMaker = ServiceMaker()
