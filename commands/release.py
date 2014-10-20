from twisted.internet.defer import returnValue
from twisted.internet.defer import DeferredList
from twisted.internet.utils import getProcessOutputAndValue
import binascii, fnmatch, os, re, shutil

config = {
    "access": "admin",
    "help": ".release [show name] (--previous) (--comment=TEXT) (--preview=TIME) || Releases the show by uploading to DCC bots, the seedbox, Nyaa, TT, and creating the blog post. Requires a .mkv and .xdelta. Use --previous for releasing a v2. See .man preview for --preview help.",
}

def command(guid, manager, irc, channel, user, show, previous = False, comment = None, preview = None):
    show = manager.master.modules["showtimes"].resolve(show)
    if not show.folder.ftp:
        raise manager.exception(u"No FTP folder given for {}".format(show.name.english))
    if not show.folder.xdcc:
        raise manager.exception(u"No XDCC folder given for {}".format(show.name.english))

    offset = 0 if previous else 1
    episode = show.episode.current + offset
    comment = u"{}: {}".format(user, comment) if comment is not None else None
    preview = preview.lower() if preview is not None else None

    # Step 0: Clean up script reviews
    if show.id in manager.master.modules["subs"].show_scripts:
        for script in manager.master.modules["subs"].show_scripts[show.id]:
            if script in manager.master.modules["subs"].reviews:
                del manager.master.modules["subs"].reviews[script]
        del manager.master.modules["subs"].show_scripts[show.id]

    # Step 1: Search FTP for complete episode, or premux + xdelta
    folder = "{}/{:02d}".format(show.folder.ftp, episode)
    manager.dispatch("update", guid, u"Caching {}".format(folder))
    yield manager.master.modules["ftp"].download(folder)
    manager.dispatch("update", guid, u"Determining last modified xdelta file")
    xdelta = yield manager.master.modules["ftp"].getLatest(folder, "*.xdelta")
    manager.dispatch("update", guid, u"Determining last modified mkv file")
    premux = yield manager.master.modules["ftp"].getLatest(folder, "*.mkv")

    if xdelta and premux:
        # Step 1b: Download premux + xdelta, merge into completed file
        irc.notice(user, u"Found xdelta and premux: {} and {}".format(xdelta, premux))

        manager.dispatch("update", guid, u"Downloading {}".format(premux))
        yield manager.master.modules["ftp"].get(folder, premux, guid)
        manager.dispatch("update", guid, u"Downloading {}".format(xdelta))
        yield manager.master.modules["ftp"].get(folder, xdelta, guid)

        manager.dispatch("update", guid, u"Merging xdelta and premux")
        out, err, code = yield getProcessOutputAndValue(manager.master.modules["utils"].getPath("xdelta3"), args=["-f","-d", os.path.join(guid, xdelta)], env=os.environ)
        if code != 0:
            manager.log(out)
            manager.log(err)
            raise manager.exception(u"Aborted releasing {}: Couldn't merge premux and xdelta.".format(show.name.english))
        irc.notice(user, u"Merged premux and xdelta")

        complete = fnmatch.filter(os.listdir(guid), "[[]*[]]*[[]*[]].mkv")
        if not complete:
            raise manager.exception(u"No completed file found after merging")
        complete = complete[0].decode("utf8")
    else:
        raise manager.exception(u"Aborted releasing {}: Couldn't find premux and xdelta.".format(show.name.english))

    # Step 1c: Verify CRC
    try:
        with open(os.path.join(guid, complete), "rb") as f:
            crc = binascii.crc32(f.read()) & 0xFFFFFFFF
    except:
        raise manager.exception(u"Aborted releasing {}: Couldn't open completed file for CRC verification.".format(show.name.english))

    normal = u"{:08X}".format(crc)
    roman = manager.master.modules["utils"].intToRoman(crc)
    detected = re.findall("\[([^]]+)\]", complete)[1].decode("utf8")

    if detected != normal and detected != roman:
        raise manager.exception(u"Aborted releasing {}: CRC failed verification. Filename = '{}', Calculated = '{}'.".format(show.name.english, detected, normal))

    # Step 1d: Determine version number
    match = re.search("(v\d+)", complete)
    version = match.group(1) if match is not None else ""

    # Step 1e: Create preview image
    preview = manager.master.modules["subs"].preview(guid, folder, complete, preview, webm, isRelease=True)
    
    # Step 2: Create torrent
    irc.notice(user, u"Creating torrent")
    try:
        torrent = manager.master.modules["torrent"].makeTorrent(guid, complete)
    except:
        manager.err("Making a torrent for {}", show.name.english)
        raise manager.exception(u"Aborted releasing {}: Couldn't create torrent.".format(show.name.english))
    irc.notice(user, u"Created torrent")

    # Step 3: Upload episode to XDCC server
    # Step 4: Upload episode to seedbox
    xdcc_deferreds = []
    xdcc_deferreds.append(manager.master.modules["ftp"].putXDCC(guid, complete, show.folder.xdcc))
    #xdcc_deferreds.append(manager.master.modules["ftp"].putXDCC2(guid, complete))
    #xdcc_deferreds.append(manager.master.modules["sftp"].putLaeVideo(guid, complete))

    irc.notice(user, u"Uploading to seedbox and XDCC")
    manager.dispatch("update", guid, u"Uploading video to seedbox")
    yield manager.master.modules["ftp"].putSeedbox(guid, complete)
    irc.notice(user, u"Uploaded to seedbox")

    # Step 5: Start seeding torrent
    manager.dispatch("update", guid, u"Uploading torrent to seedbox")
    yield manager.master.modules["ftp"].putTorrent(guid, torrent)
    irc.notice(user, u"Seeding started")

    # Step 6: Upload torrent to Nyaa
    # Step 7: Get torrent link from Nyaa
    manager.dispatch("update", guid, u"Uploading torrent to Nyaa")
    info_link, download_link = yield manager.master.modules["nyaa"].upload(guid, torrent.encode("utf8"), comment)
    irc.notice(user, u"Uploaded to Nyaa")

    # Step 8: Create blog post
    try:
        manager.dispatch("update", guid, u"Creating blog post")
        yield manager.master.modules["blog"].createPost(show, episode, version, info_link, preview["link"], comment, preview["text"])
    except:
        irc.msg(channel, u"Couldn't create blog post. We'll try again until it works! Continuing to release {} regardless.".format(show.name.english))
    else:
        irc.notice(user, u"Created blog post")

    # Step 9: Mark show finished on showtimes
    if not previous:
        try:
            manager.dispatch("update", guid, u"Marking show as finished on showtimes")
            yield manager.master.modules["showtimes"].finished(show)
        except:
            irc.msg(channel, u"Failed to mark show as finished on showtimes")

    for c in set([u"#commie-staff", u"#commie-subs", channel]):
        irc.msg(c, u"{} {:02d}{} released. Torrent @ {}".format(show.name.english, episode, version, info_link))

    # Step 10: Update the topic
    manager.dispatch("update", guid, u"Updating Topic")
    yield manager.master.modules["showtimes"].updateTopic()

    # Step 11: Wait on XDCC
    irc.notice(user, u"Waiting for XDCC")
    manager.dispatch("update", guid, u"Uploading to XDCC servers")
    yield DeferredList(xdcc_deferreds)
    #yield manager.master.modules["sftp"].putLaeTorrent(guid, torrent)
    irc.notice(user, u"Uploaded to XDCC")

    # Step 12: Add to Shiroi
    shutil.move(os.path.join(guid, complete), os.path.join(u"/var/www/shiroi.fugiman.com/watch", complete))

    returnValue(info_link)
