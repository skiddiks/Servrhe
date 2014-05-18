from twisted.internet.defer import returnValue
from wolframalpha import Result
from itertools import izip_longest
from StringIO import StringIO
import urllib

config = {
    "access": "admin",
    "help": ".GLaDOS [query] || .GLaDOS what is today's date? || Provides answers to your stupid questions."
}

endpoint = "http://api.wolframalpha.com/v2/query"

def command(guid, manager, irc, channel, user, query):
    appid = yield manager.config.get("wolfram_key")
    url = "{}?{}".format(endpoint, urllib.urlencode({"appid": appid, "input": query, "format": "plaintext"}))
    manager.dispatch("update", guid, u"Querying Wolfram Alpha")
    answer = yield manager.master.modules["utils"].fetchPage(url)
    result = Result(StringIO(answer))

    message = None
    for pod in result.pods:
        if getattr(pod, "primary", False):
            message = pod.text
            break

    if message is not None:
        # Clean it up a bit
        message = u"\n".join([u"".join(list(chunk)) for line in message.split("\n") for chunk in izip_longest(*[iter(line)]*320, fillvalue=u"")][:5])
        irc.msg(channel, message)
    else:
        url = u"http://www.wolframalpha.com/input/?" + urllib.urlencode({"i": query})
        irc.msg(channel, u"I don't know, try {}".format(url))
    returnValue(message)
