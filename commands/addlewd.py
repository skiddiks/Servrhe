from twisted.internet.defer import returnValue
from urlparse import urlparse
from os.path import splitext, basename, join
import treq, os

config = {
    "access": "public",
    "help": ".addlewd [url] (--bote) || .addlewd images.4chan.com/fuckit.jpg || Add a URL to the lewd database"
}


def command(guid, manager, irc, channel, user, url, **kwargs):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    manager.dispatch("update", guid, u"Waiting on manager.getPermissions")
    permissions = yield manager.getPermissions(user)

    manager.dispatch("update", guid, u"Waiting on alias.resolve")
    name = yield manager.master.modules["alias"].resolve(user)

    if "staff" not in permissions and name != "chuckk":
        return

    choices = {d:True for d in os.listdir("lewd")}
    directories = filter(lambda x: x.lower() in choices, kwargs.keys())
    directory = directories[0] if directories else "bestof"

    urlpath = urlparse(url)
    filename = basename(urlpath.path)
    _, file_ext = splitext(filename)

    #if urlpath.hostname not in ("images.4chan.org","i.imgur.com","i2.minus.com"):
    #    raise manager.exception(u"Invalid domain: {}".format(urlpath.hostname))

    if file_ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        raise manager.exception(u"Invalid file extension: {!s}".format(file_ext))

    manager.dispatch("update", guid, u"Downloading lewd file: {}".format(url))
    try:
        response = yield treq.get(url.encode("UTF-8"))
        data = yield treq.content(response)
    except:
        manager.err("Error downloading lewd file from {}", url)
        raise manager.exception(u"Failed to download file")

    with open(join("lewd", directory, filename), "wb") as f:
        f.write(data)

    irc.msg(channel, u"Added {} to lewd/{}".format(filename, directory))
    returnValue(join("lewd", directory, filename))
