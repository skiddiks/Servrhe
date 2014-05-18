config = {
    "access": "admin",
    "help": ".errors [line number] [filename] || Filename is the exact filename of the script, or if not specified the last filename xdelta'd."
}

def command(guid, manager, irc, channel, user, args):
    line_number, _, filename = args.partition(" ")
    try:
        line_number = int(line_number)
    except:
        raise manager.exception("Invalid line number, must be an integer")

    if not filename:
        filename = manager.master.modules["subs"].last_review

    if filename not in manager.master.modules["subs"].reviews:
        raise manager.exception(u"Given filename has not been qc'd yet. Use .xdelta first")

    review = manager.master.modules["subs"].reviews[filename]

    if line_number not in review:
        raise manager.exception(u"Given line number has no errors.")

    for line in review[line_number]:
        irc.msg(channel, line)
