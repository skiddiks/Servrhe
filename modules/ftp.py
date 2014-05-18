# -*- coding: utf-8 -*-
from twisted.internet import reactor, protocol
from twisted.internet.defer import DeferredList, inlineCallbacks, returnValue, succeed, fail
from twisted.internet.error import TimeoutError
from twisted.internet.protocol import ClientCreator
from twisted.internet.utils import getProcessOutputAndValue
from twisted.protocols.ftp import CommandFailed, FTPClient, FTPFileListProtocol
from datetime import datetime as dt
import fnmatch, os, shutil

dependencies = ["config", "commands"]

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("ftp")
        self.downloading = {}
        self.uploading = {}

    def stop(self):
        pass

    def download(self, folder):
        if folder not in self.downloading:
            self.downloading[folder] = self._download(folder)
        return self.downloading[folder]

    def upload(self, folder = "_New Encodes"):
        if folder not in self.uploading:
            self.uploading[folder] = self._upload(folder)
        return self.uploading[folder]

    def get(self, folder, filename, destination):
        source = os.path.join("mirror", folder, filename)
        destination = os.path.join(destination, filename)

        if not os.path.exists(source):
            return fail(self.master.modules["commands"].exception(u"Could not download {}".format(source)))

        shutil.copy(source, destination)
        return succeed(None)

    def put(self, folder, filename, destination = "_New Encodes"):
        source = os.path.join(folder, filename)
        destination = os.path.join("mirror", destination)

        if not os.path.exists(source):
            return fail(self.master.modules["commands"].exception(u"Could not upload {}".format(source)))

        if not os.path.exists(destination):
            os.makedirs(destination)

        shutil.copy(source, os.path.join(destination, filename))
        return succeed(None)

    def getLatest(self, folder, pattern):
        source = os.path.join("mirror", folder)

        if not os.path.exists(source):
            return fail(self.master.modules["commands"].exception(u"Could not download latest with pattern {}".format(pattern)))

        files = []
        for filename in fnmatch.filter(os.listdir(source), pattern):
            if os.path.isfile(os.path.join(source, filename)):
                files.append((os.stat(os.path.join(source, filename)).st_mtime, filename))

        if not files:
            return fail(self.master.modules["commands"].exception(u"No files matched pattern {}".format(pattern)))

        filename = sorted(files, reverse=True)[0][1]
        return succeed(filename)

    def getFonts(self, folder, destination):
        source = os.path.join("mirror", folder, "fonts")

        if not os.path.exists(source):
            return fail(self.master.modules["commands"].exception(u"Could not download fonts"))

        fonts = []
        for filename in os.listdir(source):
            if os.path.isfile(os.path.join(source, filename)):
                fonts.append(filename)
                shutil.copy(os.path.join(source, filename), os.path.join(destination, filename))

        return succeed(fonts)

    @inlineCallbacks
    def putXDCC(self, folder, filename, destination):
        user, passwd, host, port = yield self._creds("xdcc")
        root = yield self.config.get("xdccfolder")
        if root is None:
            raise self.master.modules["commands"].exception(u"No XDCC folder in config")

        url = "ftp://{}:{}@{}:{:d}/{}/{}/{}".format(user, passwd, host, port, root.encode("utf8"), destination.encode("utf8"), filename.encode("utf8"))
        filename = os.path.join(folder, filename).encode("utf8")

        yield self._put(filename, url)

    @inlineCallbacks
    def putXDCC2(self, folder, filename):
        exception = self.master.modules["commands"].exception
        user, passwd, host, port = yield self._creds("xdcc2")

        url = "ftp://{}:{}@{}:{:d}/{}".format(user, passwd, host, port, filename.encode("utf8"))
        filename = os.path.join(folder, filename).encode("utf8")

        yield self._put(filename, url)

    @inlineCallbacks
    def putSeedbox(self, folder, filename):
        exception = self.master.modules["commands"].exception
        user, passwd, host, port = yield self._creds("seed")
        destination = yield self.config.get("seedmkvfolder")
        if destination is None:
            raise exception(u"No Seedbox MKV folder in config")

        url = "ftp://{}:{}@{}:{:d}/{}/{}".format(user, passwd, host, port, destination.encode("utf8"), filename.encode("utf8"))
        filename = os.path.join(folder, filename).encode("utf8")

        yield self._put(filename, url)

    @inlineCallbacks
    def putTorrent(self, folder, filename):
        exception = self.master.modules["commands"].exception
        user, passwd, host, port = yield self._creds("seed")
        destination = yield self.config.get("seedtorrentfolder")
        if destination is None:
            raise exception(u"No Seedbox torrent folder in config")

        url = "ftp://{}:{}@{}:{:d}/{}/{}".format(user, passwd, host, port, destination.encode("utf8"), filename.encode("utf8"))
        filename = os.path.join(folder, filename).encode("utf8")

        yield self._put(filename, url)

    @inlineCallbacks
    def _creds(self, server):
        user   = yield self.config.get(server + "user")
        passwd = yield self.config.get(server + "pass")
        host   = yield self.config.get(server + "host")
        port   = yield self.config.get(server + "port")

        if user is None or passwd is None or host is None or port is None:
            raise exception(u"No " + server + " user, pass, host or port in config")

        returnValue((user.encode("utf8"), passwd.encode("utf8"), host.encode("utf8"), int(port)))

    @inlineCallbacks
    def _run(self, program, arguments, error_message):
        out, err, code = yield getProcessOutputAndValue(program, args=arguments, env=os.environ)
        if code != 0:
            self.log(out)
            self.log(err)
            raise self.master.modules["commands"].exception("{} [OUT: {}] [ERR: {}]".format(error_message, out.replace("\n"," "), err.replace("\n"," ")))

    @inlineCallbacks
    def _download(self, folder):
        user, passwd, host, port = yield self._creds("ftp")
        lftp = self.master.modules["utils"].getPath("lftp")

        args = ["-c","open","-e","mirror --continue --delete --use-pget=8 --loop --include-glob=\"*.mkv\" \"{0}\" \"mirror/{0}\"".format(folder),"ftp://{}:{}@{}:{:d}/".format(user,passwd,host,port)]
        yield self._run(lftp, args, u"LFTP fucked up :(")

        args = ["-c","open","-e","mirror --continue --delete                     --exclude-glob=\"*.mkv\" \"{0}\" \"mirror/{0}\"".format(folder),"ftp://{}:{}@{}:{:d}/".format(user,passwd,host,port)]
        yield self._run(lftp, args, u"LFTP fucked up :(")

        del self.downloading[folder]

    @inlineCallbacks
    def _upload(self, folder):
        user, passwd, host, port = yield self._creds("ftp")
        lftp = self.master.modules["utils"].getPath("lftp")

        args = ["-c","open","-e","mirror --reverse --continue \"mirror/{0}\" \"{0}\"".format(folder),"ftp://{}:{}@{}:{:d}/".format(user,passwd,host,port)]
        yield self._run(lftp, args, u"LFTP fucked up :(")

        del self.uploading[folder]

    @inlineCallbacks
    def _put(self, source, destination):
        user, passwd, host, port = yield self._creds("ftp")
        curl = self.master.modules["utils"].getPath("curl")

        args = ["--globoff", "--upload-file", source, destination]
        yield self._run(curl, args, u"CURL fucked up :(")
