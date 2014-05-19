# -*- coding: utf-8 -*-

from zope.interface import implements
from twisted.cred import portal, checkers, credentials, error as credError
from twisted.internet import defer
from twisted.web.static import File
from twisted.web.guard import BasicCredentialFactory, HTTPAuthSessionWrapper
from twisted.web.resource import IResource, Resource, ForbiddenResource
from txsockjs.factory import SockJSResource
from functools import wraps


from twisted.internet.defer import returnValue
from twisted.internet.utils import getProcessOutputAndValue
import os, re

from twisted.internet.defer import inlineCallbacks
from twisted.web.server import NOT_DONE_YET
from twisted.web.template import Element, flatten, renderer, Tag, XMLString
from collections import Counter

import hashlib, hmac, json
 
dependencies = ["progress"]

class Base(Resource):
    def __init__(self, master):
        Resource.__init__(self)
        self.master = master

class NoDirListingFile(File):
    def directoryListing(self, *args, **kwargs):
        return ForbiddenResource("You'll have to use .lewd to peruse this directory.")

class Module(Base):
    def __init__(self, master):
        Base.__init__(self, master)
        self.putChild("", self)
        self.putChild("progress", self)
        self.putChild("twilio", Twilio(master))
        self.putChild("twilio-incoming", TwilioIncoming(master))
        #self.putChild("mahoyo", Mahoyo(master))
        self.putChild("update", Update(master))
        self.putChild("lewd", NoDirListingFile("lewd"))

    def stop(self):
        pass

    def render_GET(self, request):
        return  "SOON&trade;"

class Twilio(Base):
    isLeaf = True

    def render_POST(self, request):
        irc = self.master.modules["irc"]

        if "CallSid" in request.args:
            id = request.args["CallSid"][0]
            status = request.args["CallStatus"][0].lower()

            if status == "completed":
                # Call was received
                duration = int(request.args["CallDuration"][0])
                recording = request.args["RecordingUrl"][0] + ".mp3"

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

        elif "SmsSid" in request.args:
            id = request.args["SmsSid"][0] # Might need to be "MessageSid" in the future
            status = request.args["SmsStatus"][0].lower() # Might need to be "MessageStatus" in the future

            if status == "sent":
                irc.msg("#commie-staff", u"Text #{} was sent successfully".format(id))

            elif status == "failed":
                irc.msg("#commie-staff", u"Text #{} failed".format(id))

            elif status == "sending":
                irc.msg("#commie-staff", u"Text #{} is sending".format(id))

            elif status == "queued":
                irc.msg("#commie-staff", u"Text #{} is queued".format(id))

            else:
                irc.msg("#commie-staff", u"Text #{} was lost in limbo and we aren't sure what happened to it.".format(id))

        else:
            self.master.log("Twilio API call: {!r}", request.args)

        return ""

class TwilioIncoming(Base):
    isLeaf = True

    def render_POST(self, request):
        self.handle(request).addCallback(lambda r: request.write(r)).addBoth(lambda _: request.finish())
        return NOT_DONE_YET

    @inlineCallbacks
    def handle(self, request):
        irc = self.master.modules["irc"]
        twilio = self.master.modules["twilio"]

        caller = request.args["From"][0]
        caller = yield twilio.lookup(caller)

        if "CallSid" in request.args:
            id = request.args["CallSid"][0]
            status = request.args["CallStatus"][0].lower()
            duration = int(request.args["RecordingDuration"][0])
            recording = request.args["RecordingUrl"][0] + ".mp3"

            duration = "{:d}:{:02d}".format(duration/60, duration%60)

            irc.msg("#commie-staff", u"Inbound call on the Commie Subs hotline from {} is {}. Recording lasts {} and is available at {} (#{}).".format(caller, status, duration, recording, id))

            returnValue("""
                <?xml version="1.0" encoding="UTF-8"?>
                <Response>
                    <Hangup/>
                </Response>
                """)

        elif "MessageSid" in request.args:
            body = request.args["Body"][0]
            NumMedia = int(request.args["NumMedia"][0])
            media = request.args["MediaUrl"] if NumMedia == 1 else [request.args["MediaUrl{:d}".format(N)][0] for N in range(NumMedia)]

            irc.msg("#commie-staff", u"Inbound text on the Commie Subs hotline from {}: {} {}".format(caller, body, u" ".join(media)))

        else:
            self.master.log("Twilio-Incoming API call: {!r}", request.args)

        returnValue("""
            <?xml version="1.0" encoding="UTF-8"?>
            <Response>
            </Response>
            """)

class Mahoyo(Base):
    isLeaf = True

    def render_GET(self, request):
        irc = self.master.modules["irc"]
        self.master.dispatch("irc", "message", u"#commie-staff", irc.nickname.decode("utf8"), u".mahoyo")
        return ""

class Update(Base):
    isLeaf = True

    def render_POST(self, request):
        self.handle(request).addCallback(lambda r: request.write(r)).addErrback(lambda e: self.master.err("Error: {!s}", e, cls="Web.Update")).addBoth(lambda _: request.finish())
        return NOT_DONE_YET

    @inlineCallbacks
    def handle(self, request):
        # Validate the request
        event = request.requestHeaders.getRawHeaders("X-GitHub-Event")
        signature = request.requestHeaders.getRawHeaders("X-Hub-Signature")
        if not event or not signature:
            returnValue("No Event or Signature header")

        event, signature = event[0], signature[0]
        if not event or not signature:
            returnValue("Event or Signature header empty")

        hash_method, _, signature = signature.partition("=")

        request.content.seek(0, 0)
        body = request.content.read()
        secret = yield self.master.modules["config"].get("github", "secret")
        generated = hmac.new(secret.encode("UTF-8"), body, getattr(hashlib, hash_method)).hexdigest()
        if event != "push" or generated != signature:
            self.master.log("Invalid Github webook event/signature. Event = {}, Signature = {}, Generated = {}", event, signature, generated, cls="Web.Update")
            returnValue("Invalid event or signature")

        # Update the repo
        irc = self.master.modules["irc"]
        self.master.dispatch("irc", "message", u"#commie-staff", irc.nickname.decode("utf8"), u".update")
        self.master.log("Pulling changes from Github due to webhook...", cls="Web.Update")

        # Post to staff channel informing them of the changes
        FORMATS = {
            "repo": u"\00313{}\017",
            "branch": u"\00306{}\017",
            "hash": u"\00314{}\017",
            "tag": u"\00306{}\017",
            "name": u"\00315{}\017",
            "message": u"{}",
            "url": u"\00302\037{}\017",
            "number": u"\002{:,d}\017",
        }

        args = json.loads(body)
        repo = FORMATS["repo"].format(args["repository"]["name"])

        if "ref_name" in args:
            branch_name = args["ref_name"]
        else:
            branch_name = args["ref"].replace("refs/heads/", "").replace("refs/tags/", "")
        branch = FORMATS["branch"].format(branch_name)
        tag = FORMATS["tag"].format(branch_name)

        if "base_ref" in args:
            if "base_ref_name" in args:
                base_ref_name = args["base_ref_name"]
            else:
                base_ref_name = args["base_ref"].replace("refs/heads/", "").replace("refs/tags/", "")
            base_ref = FORMATS["branch"].format(base_ref_name)
        else:
            base_ref = None

        before_sha = FORMATS["hash"].format(args["before"][:8])
        after_sha = FORMATS["hash"].format(args["after"][:8])
        pusher = FORMATS["name"].format(args["pusher"]["name"] if "pusher" in args else "somebody")
        if "distinct_commits" in args:
            distinct_commits = args["distinct_commits"]
        else:
            distinct_commits = [commit for commit in args["commits"] if commit["distinct"] and commit["message"].strip()]

        if args["created"]:
            if args["ref"].startswith("refs/tags/"):
                message = u"tagged {} at {}".format(tag, base_ref if base_ref else after_sha)
            else:
                message = u"created {}".format(branch)
                if base_ref:
                    message += u" from {}".format(base_ref)
                elif not distinct_commits:
                    message += u" at {}".format(after_sha)
                num = len(distinct_commits)
                message += " (+{} new commit{})".format(FORMATS["number"].format(num), "s" if num != 1 else "")
        elif args["deleted"]:
            message = u"\00304deleted\017 {} at {}".format(branch, before_sha)
        elif args["forced"]:
            message = u"\00304force-pushed\017 {} from {} to {}".format(branch, before_sha, after_sha)
        elif args["commits"] and not distinct_commits:
            if base_ref:
                message = "merged {} into {}".format(base_ref, branch)
            else:
                message = "fast-forwarded {} from {} to {}".format(branch, before_sha, after_sha)
        else:
            num = len(distinct_commits)
            message = "pushed {} new commit{} to {}".format(FORMATS["number"].format(num), "s" if num != 1 else "", branch)

        if args["created"] and not distinct_commits:
            url = args["repository"]["url"] + "/commits/" + branch_name
        elif args["created"] and distinct_commits:
            url = args["compare"]
        elif args["deleted"]:
            url = args["repository"]["url"] + "/commit/" + args["before"]
        elif args["forced"]:
            url = args["repository"]["url"] + "/commits/" + branch_name
        elif len(distinct_commits) == 1:
            url = distinct_commits[0]["url"]
        else:
            url = args["compare"]
        url = FORMATS["url"].format(url)

        irc.msg(u"#commie-staff", u"[{}] {} {}: {}".format(repo, pusher, message, url))

        for commit in distinct_commits:
            sha1 = FORMATS["hash"].format(commit["id"][:8])
            author = FORMATS["name"].format(commit["author"]["name"])
            message = FORMATS["message"].format(commit["message"].partition("\n")[0])
            irc.msg(u"#commie-staff", u"{}/{} {} {}: {}".format(repo, branch, sha1, author, message))

        returnValue("Success!")
