from twisted.internet.defer import returnValue

config = {
    "access": "staff",
    "help": ".post (--action=ACTION) (--args=ARGS) || .post list || Ramble as [name] would, utilizing markov chains"
}

def command(guid, manager, irc, channel, user, action = None, args = None):
    action = action.lower() if action else ""
    queue = manager.master.modules["subs"].post_queue

    if action == "list":
        posts = [u"[{}] {} {:02d}{}".format(g, p["show"].name.english, p["episode"], p["version"]) for g,p in queue.items]
        irc.msg(channel, u"Pending posts: {}".format(u", ".join(posts)))

    elif action == "cancel":
    	guid, _, args = args.partition(" ")

    	if not guid:
    		irc.msg(channel, u".post cancel [guid]")
		elif guid not in queue:
			irc.msg(channel, u"Couldn't find {} in post queue. Check `.post list` to see what's in the queue".format(guid))
		else:
			post = queue[guid]
			post["retryer"].stop()
			del queue[guid]
			irc.msg(channel, u"Post canceled: {} {:02d}{}".format(post["show"].name.english, post["episode"], post["version"]))

	else:
		irc.msg(channel, u"Usage: `.post ACTION`. Available actions: list, cancel")
