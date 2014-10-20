from twisted.internet.defer import returnValue

config = {
    "access": "staff",
    "help": ".post || .post list || Ramble as [name] would, utilizing markov chains"
}

def command(guid, manager, irc, channel, user, action = None, arg1 = None, arg2 = None, arg3 = None, arg4 = None, arg5 = None, arg6 = None):
    action = action.lower() if action else ""
    queue = manager.master.modules["blog"].post_queue

    if action == "list":
        posts = [u"[{}] {} {:02d}{}".format(g, p["show"].name.english, p["episode"], p["version"]) for g,p in queue.items()]
        irc.msg(channel, u"Pending posts: {}".format(u", ".join(posts)))

    elif action == "cancel":
        guid = arg1

        if not guid:
            irc.msg(channel, u".post cancel [guid]")
        elif not guid in queue:
            irc.msg(channel, u"Couldn't find {} in post queue. Check `.post list` to see what's in the queue".format(guid))
        else:
            post = queue[guid]
            post["retryer"].stop()
            del queue[guid]
            irc.msg(channel, u"Post canceled: {} {:02d}{}".format(post["show"].name.english, post["episode"], post["version"]))

    elif action == "create":
        show_name, version, img_link, hovertext, info_link, comment = arg1, arg2, arg3, arg4, arg5, arg6
        if version and version.startswith("http"):
            version, img_link, hovertext, info_link, comment = None, version, img_link, hovertext, info_link
        if hovertext and hovertext.startswith("http"):
            hovertext, info_link, comment = None, hovertext, info_link

        if not show_name or not img_link or not info_link:
            raise manager.exception(u".post create [show name] (version) [preview URL] (preview text) [torrent URL] (comment)")

        show = manager.master.modules["showtimes"].resolve(show_name)
        episode = show.episode.current
        version = version if version else ""
        hovertext = hovertext if hovertext else ""
        comment = u"{}: {}".format(user, comment) if comment else ""

        try:
            link = yield manager.master.modules["blog"].createPost(show, episode, version, info_link, img_link, comment, hovertext)
        except:
            irc.msg(channel, u"Failed to create blog post, but it'll be retried until it succeeds.")
        else:
            irc.msg(channel, u"Created blog post: {}".format(link))

    else:
        irc.msg(channel, u"Usage: `.post ACTION`. Available actions: list, cancel")
