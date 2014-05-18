config = {
    "access": "admin",
    "help": ".hulu [page id] || Rip subtitles from http://hulu.com/watch/PAGE_ID"
}

def command(guid, manager, irc, channel, user, page_id):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    irc.msg(channel, u"AIGHT M8, WE'LL GIT ZAT RIGHT UP READY FOR YA!")
    manager.dispatch("update", guid, u"Downloading [HULU] {}.ass".format(page_id))
    yield manager.master.modules["hulu"].rip(guid, page_id)
    irc.msg(channel, u"Ripping of [HULU] {}.ass was successful".format(page_id))
