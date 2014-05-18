# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue, CancelledError
from twisted.internet.task import LoopingCall
from txcoroutine import coroutine
import inspect, os, pkgutil, re, shutil, uuid

dependencies = ["config", "alias", "irc"]

class CommandException(Exception):
    pass

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("commands")
        self.commands = {}
        self.exception = CommandException
        self.loadCommands()

    def stop(self):
        pass

    @inlineCallbacks
    def getPermissions(self, user):
        irc = self.master.modules["irc"]
        user = yield self.master.modules["alias"].resolve(user)
        perms = yield self.master.modules["db"].alias2permissions(user)

        if "banned" in perms:
            returnValue([])
        else:
            returnValue(perms + ["public"])

    def getGUID(self):
        guid = uuid.uuid4().hex
        while os.path.exists(guid):
            guid = uuid.uuid4().hex
        os.mkdir(guid)
        return guid

    @inlineCallbacks
    def loadCommands(self):
        commands = {}
        path = yield self.config.get("path","commands")
        for loader, name, ispkg in pkgutil.iter_modules([path]):
            if ispkg:
                continue
            try:
                command = getattr(__import__(path, fromlist=[name.encode("utf8")]), name)
                reload(command)
                command.config["name"] = name
                command.config["command"] = coroutine(command.command) if inspect.isgeneratorfunction(command.command) else command.command
                args, varg, vkwarg, kwargs = inspect.getargspec(command.command)

                if args[:5] != ["guid", "manager", "irc", "channel", "user"]:
                    continue

                if kwargs:
                    boundary = -1 * len(kwargs)
                    command.config["args"] = args[5:boundary]
                    command.config["kwargs"] = args[boundary:]
                else:
                    command.config["args"] = args[5:]
                    command.config["kwargs"] = []
                command.config["varg"] = varg
                command.config["vkwarg"] = vkwarg

                if "disabled" in command.config and command.config["disabled"]:
                    continue

                commands[name] = command.config
            except:
                self.err("Failed to load {}.{}", path, name)
        self.commands = commands

    @inlineCallbacks
    def irc_message(self, channel, user, message):
        perms = yield self.getPermissions(user)
        irc = self.master.modules["irc"]

        # Only bother with commands
        if not message.startswith(".") and not (message.startswith("@") and "superadmin" in perms):
            return

        # Allow nested commands
        find_nested = re.compile("(\A|[^`])`([^`](?:.*?[^`])?)`([^`]|\Z)")

        match = find_nested.search(message)
        while match:
            subcommand = re.sub("`+", lambda x: x.group(0)[:-1], match.group(2))

            result = yield self.irc_message(channel, user, subcommand)
            if isinstance(result, Exception):
                return
            result = "" if result is None else result

            message = message[:match.start(0)] + match.group(1) + result + match.group(3) + message[match.end(0):]
            match = find_nested.search(message)

        # Parse the message into args and kwargs, respecting quoted substrings
        command_char = message[0]
        parts = message[1:].split(" ")
        filtered = []
        kwargs = {}
        while parts:
            arg = parts.pop(0)
            if arg.startswith("--"):
                name, _, value = arg[2:].partition("=")
                name = name.replace("-","_").lower()
                if value:
                    if value.startswith('"'):
                        if value.endswith('"'):
                            value = value[1:-1]
                        else:
                            vparts = [value[1:]]
                            while parts:
                                arg = parts.pop(0)
                                if arg.endswith('"'):
                                    vparts.append(arg[:-1])
                                    break
                                else:
                                    vparts.append(arg)
                            value = " ".join(vparts)
                else:
                    value = True
                kwargs[name] = value
            else:
                filtered.append(arg)
        message = " ".join(filtered).strip()
        args = []
        while message:
            if message.startswith('"'):
                arg, _, message = message[1:].partition('" ')
                if not message and arg.endswith('"'):
                    arg = arg[:-1]
                args.append(arg)
            else:
                arg, _, message = message.partition(" ")
                args.append(arg)

        # Add in admin_mode after parsing, so that users can't override it
        kwargs["admin_mode"] = command_char == "@"

        # You'd be surprised how often this happens
        if not args:
            return

        # Extract command name, checking if it is a reversed command
        command = args.pop(0).lower()
        if command.startswith("un"):
            command = command[2:]
            kwargs["reverse"] = True
        else:
            kwargs["reverse"] = False

        # Exchange command name for command dictionary
        if command not in self.commands:
            return
        command = self.commands[command]

        # Check access before we print help text. It avoids confusion
        if command["access"] not in perms or (kwargs["admin_mode"] and "superadmin" not in perms):
            return

        # Ensure that if they tried a reverse command, that it is actually reversible
        if kwargs["reverse"] and "reverse" not in command["kwargs"]:
            return

        # Filter kwargs
        if not command["vkwarg"]:
            filtered = {}
            for arg in command["kwargs"]:
                if arg in kwargs:
                    filtered[arg] = kwargs[arg]
            kwargs = filtered

        # Fix up args
        arglen = len(command["args"])
        if arglen > len(args):
            irc.msg(channel, command["reverse_help"] if "reverse" in kwargs and kwargs["reverse"] else command["help"])
            return

        if not command["varg"]:
            if arglen:
                args = args[:arglen-1] + [" ".join(args[arglen-1:])]
            else:
                # As a special case, if there are no args, map args to kwargs
                args = dict(zip(command["kwargs"], args))
                args.update(kwargs)
                kwargs = args
                args = []

        # Get a working directory & identifier
        guid = self.getGUID()

        # Run the command
        self.log("Running command: {} {} {} {} {!r} {!r}", command["name"], guid, channel, user, args, kwargs)
        process = maybeDeferred(command["command"], guid, self, irc, channel, user, *args, **kwargs)
        self.dispatch("start", process, command["name"], guid, channel, user, args, kwargs)
        try:
            result = yield process
        except CommandException as e:
            irc.msg(channel, unicode(e))
            result = e
        except CancelledError as e:
            irc.msg(channel, u"{} on behalf of {} was cancelled.".format(command["name"], user))
            result = e
        except Exception as e:
            self.err("{} on behalf of {} failed unexpectedly.", command["name"], user)
            irc.msg(channel, u"Fugiman: {} on behalf of {} failed unexpectedly.".format(command["name"], user))
            result = e
        self.dispatch("finish", guid)

        # Clean up
        shutil.rmtree(guid)

        returnValue(result)
