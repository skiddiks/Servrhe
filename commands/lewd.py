from twisted.internet.defer import returnValue
import random, json, os

config = {
    "access": "public",
    "help": ".lewd (--top) (--peak) (--duwang) (--board=BOARD) || .lewd --board=h || Provides lewdness for your enjoyment"
}

def command(guid, manager, irc, channel, user, top = False, peak = False, duwang = False, board = None, **kwargs):
    irc.msg(channel, u"This command is currently disabled due to the upgrade to v5. It'll return shortly. Thank you for your patience.")
    return
    
    everything = set([
        "a","c","w","m","cgl","cm","f","n","jp","vp",
        "v","vg","vr","co","g","tv","k","o","an","tg","sp","asp","sci","int","out","toy",
        "i","po","p","ck","ic","wg","mu","fa","3","gd","diy","wsg",
        "s","hc","hm","h","e","u","d","y","t","hr","gif",
        "trv","fit","x","lit","adv","lgbt","mlp",
        "b","r","r9k","pol","soc","s4s"])

    blacklist = set(["mlp","b","v","3","gif","s4s"])
    whitelist = everything - blacklist

    choices = {d:["http://servrhe.fugiman.com/lewd/{}/{}".format(d,f) for f in os.listdir(os.path.join("lewd", d))] for d in os.listdir("lewd")}
    messages = {
        "fugi": u"Fugi recommends for {0}'s viewing pleasure, {1}",
        "bote": u"Some top bote for {0}'s enjoyment: {1}",
        "bestof": u"The lewd curators of #Commie-Subs hopes to delight {0} with this classic vintage: {1}",
        "orcus": u".kb {0} {1}"
    }

    if kwargs and not board:
        boards = filter(lambda x: x.lower() in everything or x.lower() in choices, kwargs.keys())
        if boards:
            board = boards[0]

    if board:
        board = board.lower()

        if board in choices:
            url = random.choice(choices[board])
            message = messages.get(board, u"We hope {{0}} enjoy's some lewd from our {} cache: {{1}}".format(board))
            irc.msg(channel, message.format(user, url))
            returnValue(url)

        if board not in whitelist:
            irc.msg(channel, "No lewd found in /{}/".format(board))
            return

        message = u"{{0}} have some /{}/ lewd: {{1}}".format(board)
    elif duwang is True:
        #board = u"jp"
        board = random.choice(list(whitelist))
        message = u"{0} you are a lood duwang: {1}"
    elif peak is True:
        board = u"hr"
        message = u"PEAK LEWD for {0}: {1}"
    elif top is True:
        board = u"u"
        message = u"Top Lewd for {0}: {1}"
    else:
        board = u"e"
        message = u"Lewd for {0}: {1}"

    manager.dispatch("update", guid, u"Fetching /{}/ front-page".format(board))
    data = yield manager.master.modules["utils"].fetchPage("http://api.4chan.org/{}/0.json".format(board))
    data = json.loads(data)

    images = set()
    for thread in data["threads"]:
        for post in thread["posts"]:
            if "ext" in post:
                images.add(u"http://images.4chan.org/{}/src/{}{}".format(board, post["tim"], post["ext"]))

    if not images:
        irc.msg(channel, "No lewd found in /{}/".format(board))
        return

    url = random.choice(list(images))
    irc.msg(channel, message.format(user, url))
    returnValue(url)
