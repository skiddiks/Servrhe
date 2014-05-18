config = {
    "access": "staff",
    "help": ".fugipls [do this thing] || .fugipls Actually fix the bot || Adds something to fugi's to-do list"
}

import re

def command(guid, manager, irc, channel, user, next = False, done = False, rotate = False, dump = False, *args):
    manager.dispatch("update", guid, u"Waiting on config.get")
    requests = yield manager.config.get("fugipls_requests", [])
    args = list(args)

    if dump is not True and dump is not False:
        args.insert(0, dump)
        dump = False

    if rotate is not True and rotate is not False and not re.match("^\d+$", rotate):
        args.insert(0, rotate)
        rotate = False

    if done is not True and done is not False and not re.match("^\d+$", done):
        args.insert(0, done)
        done = False

    if next is not True and next is not False:
        args.insert(0, next)
        next = False

    done = int(done)
    rotate = int(rotate)

    if args:
        pls = u"<{}>: {}".format(user, u" ".join(args))
        requests.append(pls)
        irc.msg(channel, u"Added \"{}\" to the to-do list".format(pls))

    if (next or done or rotate or dump) and not requests:
        raise manager.exception(u"No requests have been submitted")

    if done or rotate:
        remove = done - 1 if done else rotate - 1
        if remove < len(requests):
            removed = requests.pop(remove)
            if done:
                irc.msg(channel, u"Marked \"{}\" as completed".format(removed))
            else:
                irc.msg(channel, u"Moved \"{}\" to the back of the list.".format(removed))
                requests.append(removed)
        else:
            irc.msg(channel, u"There is no request #{:,d}".format(remove + 1))

    if dump:
        irc.msg(channel, u"\n".join([u"[{:02d}] {}".format(i+1,m) for i,m in enumerate(requests)]))
    elif next:
        irc.msg(channel, u"Next on the to-do list: \"{}\"".format(requests[0]))

    manager.dispatch("update", guid, u"Waiting on config.set")
    yield manager.config.set("fugipls_requests", requests)
