# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from bs4 import BeautifulSoup
import treq, re, json

dependencies = ["config", "irc"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("4chan")
        self.threads = {}
        self.initial = True
        self.check_loop = LoopingCall(self.check)
        #self.check_loop.start(300)

    def stop(self):
        if self.check_loop is not None and self.check_loop.running:
            self.check_loop.stop()
            self.check_loop = None

    @inlineCallbacks
    def check(self):
        # Hax
        try:
            irc = self.master.modules["irc"]
            words = yield self.config.get("words", [])

            response = yield treq.get("http://a.4cdn.org/a/threads.json")
            threads = yield treq.json_content(response)

            nthreads, check = {}, []
            for o in threads:
                for t in o["threads"]:
                    nthreads[t["no"]] = t["last_modified"]
                    if t["no"] not in self.threads:
                        self.threads[t["no"]] = 0
                    if t["last_modified"] > self.threads[t["no"]]:
                        check.append(t["no"])

            if not self.initial:
                threads = []
                for t in check:
                    response = yield treq.get("http://a.4cdn.org/a/res/{:d}.json".format(t))
                    if response.code == 200:
                        data = yield treq.json_content(response)
                        found, posts = set(), []
                        for p in data["posts"]:
                            if p["time"] > self.threads[t] and "com" in p:
                                f = set(filter(lambda x: re.search(r"\b" + x.lower() + r"\b", p["com"].lower()), words))
                                if f:
                                    found.update(f)
                                    posts.append((p["no"], p["com"]))
                        if found and posts:
                            threads.append((t, found, posts))
                if len(threads) < 5:
                    for t, found, posts in threads:
                        p, also = posts[0], (u"(also {} in same thread)".format(", ".join([str(x[0]) for x in posts[1:]])) if posts[1:] else u"")
                        url = "https://archive.foolz.us/a/thread/{:d}/#{:d}".format(t, p[0])
                        #response = yield treq.post("https://www.googleapis.com/urlshortener/v1/url?key="+API_KEY, json.dumps({"longUrl": url}), headers={'Content-Type': ['application/json']})
                        #data = yield treq.json_content(response)
                        #url = data["id"]
                        excerpt = p[1].replace("<br>", "\n")
                        excerpt = BeautifulSoup(excerpt).get_text()
                        excerpt = re.sub("\s+", " ", excerpt)
                        excerpt = excerpt if len(excerpt) <= 100 else excerpt[:97]+"..."
                        irc.msg(u"#commie-subs", u"\u00039>{} mentioned on /a/ at {} [{}] {}".format(u", ".join(found), url, excerpt, also))
                else:
                    t, found = [str(x[0]) for x in threads], reduce(lambda a,b: a|b, [x[1] for x in threads])
                    irc.msg(u"#commie-subs", u"\u00039>{} flooded /a/ in threads {}".format(u", ".join(found), u", ".join(t)))

            self.threads = nthreads
            self.initial = False
        except:
            self.err(u"4chan module broke horribly :(")
