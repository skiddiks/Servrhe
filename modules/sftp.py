from twisted.internet.defer import Deferred, succeed, inlineCallbacks

from twisted.conch.ssh.common import NS
from twisted.conch.scripts.cftp import ClientOptions
from twisted.conch.ssh.filetransfer import FileTransferClient, FXF_WRITE, FXF_CREAT, FXF_TRUNC
from twisted.conch.client.connect import connect
from twisted.conch.client.default import SSHUserAuthClient, verifyHostKey
from twisted.conch.ssh.connection import SSHConnection
from twisted.conch.ssh.channel import SSHChannel

import os

dependencies = []

class SFTPUserAuthClient(SSHUserAuthClient):
    def getPassword(self, prompt = None):
        if "password" in self.options:
            return succeed(self.options["password"])
        return SSHUserAuthClient.getPassword(self, prompt)

class SFTPSession(SSHChannel):
    name = 'session'

    @inlineCallbacks
    def channelOpen(self, whatever):
        yield self.conn.sendRequest(self, 'subsystem', NS('sftp'), wantReply=True)
        client = FileTransferClient()
        client.makeConnection(self)
        self.dataReceived = client.dataReceived
        self.conn._sftp.callback(client)

class SFTPConnection(SSHConnection):
    def serviceStarted(self):
        self.openChannel(SFTPSession())

class Module(object):
    def __init__(self, master):
        self.master = master
        self.config = master.modules["config"].interface("sftp")

    def stop(self):
        pass

    @inlineCallbacks
    def _creds(self):
        user   = yield self.config.get("user")
        passwd = yield self.config.get("pass")
        host   = yield self.config.get("host")
        port   = yield self.config.get("port")

        if user is None or passwd is None or host is None or port is None:
            raise exception(u"No SFTP user, pass, host or port in config")

        returnValue((user.encode("utf8"), passwd.encode("utf8"), host.encode("utf8"), int(port)))

    def acquireConnection(self, user, password, host, port):
        options = ClientOptions()
        options['user'] = user
        options['password'] = password
        options['host'] = host
        options['port'] = port
        conn = SFTPConnection()
        conn._sftp = Deferred()
        auth = SFTPUserAuthClient(user, options, conn)
        connect(host, port, options, verifyHostKey, auth)
        return conn._sftp

    @inlineCallbacks
    def put(self, client, folder, filename, destination = None):
        local = os.path.join(folder, filename).encode("utf8")
        remote = os.path.join(destination, filename).encode("utf8")
        rfile = yield client.openFile(remote, FXF_WRITE | FXF_CREAT | FXF_TRUNC, {})
        with open(local, "rb") as f:
            yield rfile.writeChunk(0, f.read())
        yield rfile.close()

    @inlineCallbacks
    def putLae(self, folder, filename, destination = None):
        user, passwd, host, port = yield self._creds()
        client = yield self.acquireConnection(user, passwd, host, port)
        yield self.put(client, folder, filename, destination)
        client.transport.loseConnection()

    def putLaeVideo(self, folder, filename):
        return self.putLae(folder, filename, "ssd")

    def putLaeTorrent(self, folder, filename):
        return self.putLae(folder, filename, ".")
