# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import FileBodyProducer
from twisted.web.http_headers import Headers
from StringIO import StringIO
import base64, json, urllib, hmac, hashlib

dependencies = ["config", "commands", "utils"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("twilio")

    def stop(self):
        pass

    @inlineCallbacks
    def resolve(self, name):
        exception = self.master.modules["commands"].exception
        number = yield self.master.modules["db"].alias2number(name)
        if not number:
            raise exception(u"No known number for {}".format(name))
        returnValue(number)

    @inlineCallbacks
    def lookup(self, number):
        number = number.replace("+", "").replace("-", "")
        name = yield self.master.modules["db"].number2userName(number)
        returnValue(name or number)

    @inlineCallbacks
    def call(self, number, who, what):
        exception = self.master.modules["commands"].exception
        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        us = yield self.config.get("number")

        if user is None or passwd is None or us is None:
            raise exception(u"No Twilio username, password, or number in config")

        twiml = """
            <Response>
                <Say>Hey faggot, {0} would like you to know</Say>
                <{2}>{1}</{2}>
                <Say>You have ten seconds to respond</Say>
                <Pause length="10"/>
            </Response>
            """.format(who, what, "Play" if what.startswith("http") else "Say")

        url = "https://api.twilio.com/2010-04-01/Accounts/{}/Calls.json".format(user)
        creds = "Basic {}".format(base64.b64encode("{}:{}".format(user, passwd)))
        twimlet = "http://twimlets.com/echo?{}".format(urllib.urlencode({"Twiml": twiml}))
        data = urllib.urlencode({
                "From": us,
                "To": number,
                "Url": twimlet,
                "Method": "GET",
                "Record": "true",
                "Timeout": "20",
                "StatusCallback": "http://servrhe.fugiman.com/twilio/"
            })

        response = yield self.master.agent.request("POST", url, Headers({'Content-Type': ['application/x-www-form-urlencoded'], 'Authorization': [creds]}), FileBodyProducer(StringIO(data)))
        body = yield self.master.modules["utils"].returnBody(response)
        data = json.loads(body)

        if response.code not in (200, 201):
            self.log("{!r}", data)
            raise exception(u"Error placing call")
        
        returnValue(data["sid"])

    @inlineCallbacks
    def text(self, number, who, what):
        exception = self.master.modules["commands"].exception
        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        us = yield self.config.get("number")

        if user is None or passwd is None or us is None:
            raise exception(u"No Twilio username, password, or number in config")

        url = "https://api.twilio.com/2010-04-01/Accounts/{}/Messages.json".format(user)
        creds = "Basic {}".format(base64.b64encode("{}:{}".format(user, passwd)))
        data = urllib.urlencode({
                "From": us,
                "To": number,
                "Body": u"{}: {}".format(who, what).encode("UTF-8"),
                "StatusCallback": "http://servrhe.fugiman.com/twilio/"
            })

        response = yield self.master.agent.request("POST", url, Headers({'Content-Type': ['application/x-www-form-urlencoded'], 'Authorization': [creds]}), FileBodyProducer(StringIO(data)))
        body = yield self.master.modules["utils"].returnBody(response)
        data = json.loads(body)

        if response.code not in (200, 201):
            self.log("{!r}", data)
            raise exception(u"Error placing call")
        
        returnValue(data["sid"])

    @inlineCallbacks
    def validate(self, request):
        url = request.uri
        data = sorted(request.args.items())
        signature = request.requestHeaders.getRawHeaders("X-Twilio-Signature")
        signature = signature[0] if signature else None
        auth_token = yield self.config.get("pass")

        for key, values in data:
            for value in sorted(values):
                url += key + value

        generated = base64.b64encode(hmac.new(auth_token.encode("UTF-8"), url, hashlib.sha1).digest())

        returnValue(signature == generated)
