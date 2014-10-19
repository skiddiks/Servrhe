config = {
    "access": "admin",
    "help": ".ftpinfo [person] || .ftpinfo foogiman || Gives a user access to the FTP"
}

def command(guid, manager, irc, channel, user, victim):
    creds = yield manager.master.modules["ftp"]._creds("ftp")
    irc.notice(victim, u"The FTP server url is: {}:{}@{}:{}".format(*creds))
