config = {
    "access": "public",
    "help": ".en [nippon] || .en MOONRUNES || Prints the English title of the show"
}

def command(guid, manager, irc, channel, user, nippon):
    for show in manager.master.modules["showtimes"].shows.values():
        if nippon == show.name.japanese:
            irc.msg(channel, u"{} -> {}".format(show.name.japanese, show.name.english))
            return show.name.english
    
    irc.msg(channel, u"There is no English title for {} stored in showtimes.".format(nippon))
