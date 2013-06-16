# -*- coding: utf-8 -*-

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.xmlrpc import Proxy
from bs4 import BeautifulSoup
import xmlrpclib

dependencies = ["config", "commands"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("blog")

    def stop(self):
        pass

    @inlineCallbacks
    def createPost(self, show, episode, version, info_link, img_link, comment = None):
        end = " END" if episode == show.episode.total else ""
        exception = self.master.modules["commands"].exception
        img = '<img src="{}" style="width: 100%; border-radius: 5px;" />'.format(img_link)
        comment = "<br><br>{}".format(comment.encode("utf8")) if comment is not None else ""

        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        if user is None or passwd is None:
            raise exception(u"No blog username or password in config")

        blog = Proxy("http://commiesubs.com/xmlrpc.php")
        blog.queryFactory.noisy = False
        slug = show.blog.split("/")[-2]
        categories = ["The Bread Lines"]
        result = yield blog.callRemote("wp.getTerms", 0, user, passwd, "category")
        for term in result:
            if term["slug"] == slug:
                categories.append(term["name"])

        try:
            yield blog.callRemote("wp.newPost",
                0, # Blog ID
                user, # Username
                passwd, # Password
                { # Content
                    "post_type": "post",
                    "post_status": "publish",
                    "comment_status": "open",
                    "post_title": "{} {:02d}{}{}".format(show.name.english, episode, version, end),
                    "post_content": "{}<br><br><a href=\"{}\">Torrent</a>{}".format(img, info_link, comment),
                    "terms_names": {"category": categories}
                }
            )
        except:
            raise exception(u"Couldn't publish blog post")

    @inlineCallbacks
    def uploadImage(self, name, data):
        exception = self.master.modules["commands"].exception

        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        if user is None or passwd is None:
            raise exception(u"No blog username or password in config")

        blog = Proxy("http://commiesubs.com/xmlrpc.php")
        blog.queryFactory.noisy = False

        try:
            data = yield blog.callRemote("wp.uploadFile",
                0, # Blog ID
                user, # Username
                passwd, # Password
                { # Content
                    "name": name,
                    "type": "image/jpeg",
                    "bits": xmlrpclib.Binary(data),
                    "overwrite": True
                }
            )
        except:
            raise exception(u"Couldn't upload image")

        returnValue(data["url"])

    @inlineCallbacks
    def updateMahoyo(self, progress):
        progress = BeautifulSoup(progress)
        exception = self.master.modules["commands"].exception

        user = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        if user is None or passwd is None:
            raise exception(u"No blog username or password in config")

        blog = Proxy("http://commiesubs.com/xmlrpc.php")
        blog.queryFactory.noisy = False

        post = yield blog.callRemote("wp.getPost", 0, user, passwd, 8367)
        content = BeautifulSoup(post["post_content"])

        old = content.find(class_="progress")
        new = progress.find(class_="progress")
        old.replace_with(new)
        content = content.encode(formatter="html")

        try:
            yield blog.callRemote("wp.editPost", 0, user, passwd, 8367, {"post_content": content})
        except:
            raise exception(u"Couldn't update post")
