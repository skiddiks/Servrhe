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

import hmac
 
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
        self.putChild("mahoyo", Mahoyo(master))
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
        self.handle(request).addCallback(lambda r: request.write(r) and request.finish())
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
        self.update(request)
        return ""

    @inlineCallbacks
    def update(self, request):
        event = request.requestHeaders.getRawHeaders("X-Github-Event")
        signature = request.requestHeaders.getRawHeaders("X-Github-Signature")
        if not event or not signature:
            return

        event, signature = event[0], signature[0]
        if not event or not signature:
            return

        hash_method, _, signature = signature.partition("=")

        request.content.seek(0, 0)
        body = request.content.read()
        secret = yield self.master.modules["config"].get("github", "secret")
        generated = hmac.new(secret, body, hash_method).hexdigest()
        if event != "push" or generated != signature:
            self.master.log("Invalid Github webook event/signature. Event = {}, Signature = {}, Generated = {}", event, signature, generated, cls="Web.Update")
            return

        irc = self.master.modules["irc"]
        self.master.dispatch("irc", "message", u"#commie-staff", irc.nickname.decode("utf8"), u".update")
