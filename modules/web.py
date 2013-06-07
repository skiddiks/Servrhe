# -*- coding: utf-8 -*-

from zope.interface import implements
from twisted.cred import portal, checkers, credentials, error as credError
from twisted.internet import defer
from twisted.web.resource import IResource
from twisted.web.guard import BasicCredentialFactory, HTTPAuthSessionWrapper
from functools import wraps
 
class PasswordDictChecker:
    implements(checkers.ICredentialsChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)
 
    def __init__(self, users, level):
        self.users = users
        self.level = level
 
    def requestAvatarId(self, credentials):
        username = credentials.username
        if self.users.has_key(username):
            if credentials.password == self.users[username][0]:
                if self.level in self.users[username][1]:
                    return defer.succeed(username)
                else:
                    return defer.fail(credError.UnauthorizedLogin("Access level is too low"))
            else:
                return defer.fail(credError.UnauthorizedLogin("Bad password"))
        else:
            return defer.fail(credError.UnauthorizedLogin("No such user"))
 
class HttpPasswordRealm(object):
    implements(portal.IRealm)
 
    def __init__(self, myresource):
        self.myresource = myresource
    
    def requestAvatar(self, user, mind, *interfaces):
        if IResource in interfaces:
            # myresource is passed on regardless of user
            return (IResource, self.myresource, lambda: None)
        raise NotImplementedError()

def protect(level="public"):
    users = {"fugiman": ("fuckyoulae", ("public", "admin")), "commie": ("rheisafagget", ("public",))}

    def make(resource):

        def wrapper(*args, **kwargs):
            r = resource(*args, **kwargs)
            checker = PasswordDictChecker(users, level)
            realm = HttpPasswordRealm(r)
            p = portal.Portal(realm, [checker])
            credentialFactory = BasicCredentialFactory("ServrheV4")
            return HTTPAuthSessionWrapper(p, [credentialFactory])

        return wrapper

    return make

from twisted.web.resource import Resource

dependencies = []

class Base(Resource):
    def __init__(self, master):
        Resource.__init__(self)
        self.master = master

class Module(Base):
    def __init__(self, master):
        Base.__init__(self, master)
        self.putChild("twilio", Twilio(master))
        self.putChild("mahoyo", Mahoyo(master))
        self.putChild("aliases", AliasResource(master))
        self.putChild("alias_admin", AliasAdmin(master))

    def stop(self):
        pass

class Twilio(Base):
    isLeaf = True

    def render_POST(self, request):
        irc = self.master.modules["irc"]
        id = request.args["CallSid"][0]
        status = request.args["CallStatus"][0].lower()

        if status == "completed":
            # Call was received
            duration = int(request.args["CallDuration"][0])
            recording = request.args["RecordingUrl"][0]

            duration = "{:d}:{:02d}".format(duration/60, duration%60)
            irc.msg("#commie-staff", u"Call #{} lasted {} and the recording is available at {}".format(id, duration, recording))

        elif status == "no-answer":
            # Call wasn't received
            irc.msg("#commie-staff", u"Call #{} was never answered. Better luck next time.".format(id))

        elif status == "failed":
            # Something went wrong
            irc.msg("#commie-staff", u"Call #{} was failed miserably and likely wasn't received.".format(id))

        else:
            # We don't know what happened
            irc.msg("#commie-staff", u"Call #{} was lost in limbo and we aren't sure what happened to it.".format(id))

        return ""

from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import os, re

class Mahoyo(Base):
    isLeaf = True

    def render_GET(self, request):
        irc = self.master.modules["irc"]
        self.master.dispatch("irc", "message", u"#commie-staff", irc.nickname.decode("utf8"), u".mahoyo")
        return ""

from twisted.internet.defer import inlineCallbacks
from twisted.web.server import NOT_DONE_YET
from twisted.web.template import Element, flatten, renderer, Tag, XMLString
from collections import Counter

ALIAS_TEMPLATE = """
<html xmlns:t="http://twistedmatrix.com/ns/twisted.web.template/0.1">
    <head>
        <meta charset="utf-8" />
        <meta http-equiv="X-UA-Compatible" content="IE=edge,chrome=1" />
        <title>
            Alias Listing
        </title>
        <link rel="stylesheet" href="//fonts.googleapis.com/css?family=Ubuntu:400" />
        <script src="//cdnjs.cloudflare.com/ajax/libs/jquery/2.0.1/jquery.js"></script>
        <style>
            html {
                color: #333;
                font-family: Ubuntu, sans-serif;
                font-size: 16px;
                line-height: 22px;
            }
            table {
                width: 960px;
                margin: 20px auto;
                border-collapse: collapse;
            }
            tr {
                height: 34px;
                border-bottom: 1px solid #E8E8E8;
            }
            th {
                color: #AAA;
                font-weight: normal;
                font-size: 13px;
                line-height: 18px;

            }
            td:first-child {
                padding-right: 10px;
            }
            a {
                color: #333;
                text-decoration: none;
            }
            a:hover {
                color: orange;
            }
            .plus {
                position: relative;
                top: 2px;
                font-size: 28px;
                line-height: 10px;
            }
            #create {
                position: fixed;
                top: 100px;
                left: 50%;
                margin-left: -560px;
                font-size: 6em;
            }
            #warning {
                margin: auto;
                width: 960px;
                padding: 10px;
                background: pink;
                color: red;
                font-weight: bold;
            }
            button {
                display: block;
                width: 920px;
                margin: auto;
                padding: 20px;
                font-size: 3em;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <a id="create" href="javascript:create()">+</a>
        <div t:render="duplicates" />
        <table>
            <tr><th></th><th>Master</th><th>Slaves</th></tr>
            <tr t:render="line"><td><a><t:attr name="href"><t:slot name="link" /></t:attr>&#x2716;</a></td><td><t:slot name="master" /></td><td><t:slot name="slaves" /></td></tr>
        </table>
        <form action="/alias_admin"><input type="hidden" name="action" value="fix_markov" /><button>Fix Markov Database</button></form>
        <script>
        //<![CDATA[
            function create() {
                var names = prompt("Nicks to group? (Master first)");
                if(names)
                    window.location = "/alias_admin?action=add_master&names=" + names;
            }
            function add(master) {
                var slave = prompt("New slave name?");
                if(slave)
                    window.location = "/alias_admin?action=add_slave&master=" + master + "&slave=" + slave;
            }
            function edit(old) {
                var neww = prompt("New master name?", old);
                if(neww)
                    window.location = "/alias_admin?action=edit_master&old=" + old + "&new=" + neww;
            }
        //]]>
        </script>
    </body>
</html>
"""

class AliasElement(Element):
    loader = XMLString(ALIAS_TEMPLATE)

    @renderer
    @inlineCallbacks
    def duplicates(self, request, tag):
        documents = yield self.master.modules["alias"].db.find()
        duplicates = sorted([x for x,y in Counter([x for d in documents for x in d["slaves"]]).items() if y > 1])

        if duplicates:
            returnValue(tag("Warning! Duplicates found: {}".format(", ".join(duplicates)), id="warning"))
        else:
            returnValue(tag)

    @renderer
    @inlineCallbacks
    def line(self, request, tag):
        tags = []
        documents = yield self.master.modules["alias"].db.find()
        documents.sort(key=lambda d: d["master"])
        for document in documents:
            link_tag = "/alias_admin?action=delete_master&master={}".format(document["master"])

            master_tag = Tag("a")(document["master"], href="javascript:edit('{}')".format(document["master"]))

            slaves = [Tag("a")(name, href="/alias_admin?action=delete_slave&master={}&slave={}".format(document["master"], name)) for name in sorted(list(set(document["slaves"])))]
            commas = [Tag("")(", ")] * len(slaves)
            slaves = [t for pair in zip(slaves, commas) for t in pair]
            slaves.append(Tag("a")(Tag("span")("+", class_="plus"), Tag("")("Alias"), href="javascript:add('{}')".format(document["master"])))
            slave_tag = Tag("")(*slaves)

            tags.append(tag.clone().fillSlots(link=link_tag, master=master_tag, slaves=slave_tag))
        returnValue(tags)

class AliasResource(Base):
    isLeaf = True

    def render_GET(self, request):
        request.write("<!doctype html>\n")
        element = AliasElement()
        element.master = self.master
        flatten(request, element, request.write).addCallback(lambda _: request.finish())
        return NOT_DONE_YET

@protect("admin")
class AliasAdmin(Base):
    isLeaf = True

    def render_GET(self, request):
        if "action" not in request.args or not request.args["action"]:
            return "Invalid action"
        action = request.args["action"][0]

        if action == "add_master":
            if "names" not in request.args or not request.args["names"]:
                return "Invalid names"
            names = request.args["names"][0]

            master, _, slaves = names.partition(" ")
            if not slaves:
                return "No slaves given"

            slaves = [master] + slaves.split(" ")
            document = {"master": master, "slaves": slaves}

            self.master.modules["alias"].db.save(document, safe=True).addBoth(lambda _: request.finish())

        elif action == "add_slave":
            if "master" not in request.args or not request.args["master"]:
                return "Invalid master"
            master = request.args["master"][0]
            if "slave" not in request.args or not request.args["slave"]:
                return "Invalid slave"
            slave = request.args["slave"][0]

            def addSlave(documents):
                if not documents:
                    return request.finish()

                document = documents[0]
                document["slaves"].append(slave)
                self.master.modules["alias"].db.save(document, safe=True).addBoth(lambda _: request.finish())

            self.master.modules["alias"].db.find({"master": master}).addCallback(addSlave)

        elif action == "edit_master":
            if "old" not in request.args or not request.args["old"]:
                return "Invalid old master"
            old = request.args["old"][0]
            if "new" not in request.args or not request.args["new"]:
                return "Invalid new master"
            new = request.args["new"][0]

            def editMaster(documents):
                if not documents:
                    return request.finish()

                document = documents[0]
                document["master"] = new
                self.master.modules["alias"].db.save(document, safe=True).addBoth(lambda _: request.finish())

            self.master.modules["alias"].db.find({"master": old}).addCallback(editMaster)

        elif action == "delete_master":
            if "master" not in request.args or not request.args["master"]:
                return "Invalid master"
            master = request.args["master"][0]

            self.master.modules["alias"].db.remove({"master": master}, safe=True).addBoth(lambda _: request.finish())

        elif action == "delete_slave":
            if "master" not in request.args or not request.args["master"]:
                return "Invalid master"
            master = request.args["master"][0]
            if "slave" not in request.args or not request.args["slave"]:
                return "Invalid slave"
            slave = request.args["slave"][0]

            def deleteSlave(documents):
                if not documents:
                    return request.finish()

                document = documents[0]
                document["slaves"].remove(slave)
                self.master.modules["alias"].db.save(document, safe=True).addBoth(lambda _: request.finish())

            self.master.modules["alias"].db.find({"master": master}).addCallback(deleteSlave)

        elif action == "fix_markov":
            @inlineCallbacks
            def fixMarkov(documents):
                for d in documents:
                    yield self.master.modules["markov"].db.update({"name": {"$in": d["slaves"]}}, {"$set": {"name": d["master"]}}, multi=True, safe=True)
                request.finish()

            self.master.modules["alias"].db.find().addCallback(fixMarkov)

        else:
            return "Invalid Action"

        request.redirect("/aliases")
        return NOT_DONE_YET
