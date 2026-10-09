"""One writer per data directory; another launch activates the existing window."""
import hashlib,os
from pathlib import Path
from PySide6.QtCore import QObject,QLockFile,QStandardPaths,Signal
from PySide6.QtNetwork import QLocalServer,QLocalSocket


class SingleInstance(QObject):
    activated=Signal()

    def __init__(self,data):
        super().__init__()
        key=hashlib.sha256((str(Path(data).resolve()).casefold()+os.environ.get('USERNAME','')).encode()).hexdigest()[:24]
        self.name='GameCloudSave-'+key
        runtime=Path(QStandardPaths.writableLocation(QStandardPaths.TempLocation))/'GameCloudSave'
        runtime.mkdir(exist_ok=True)
        self.lock=QLockFile(str(runtime/(key+'.lock')))
        self.lock.setStaleLockTime(0)
        self.server=QLocalServer(self)

    def acquire(self):
        if not self.lock.tryLock(0):
            client=QLocalSocket()
            client.connectToServer(self.name)
            if client.waitForConnected(1200):
                client.write(b'activate');client.waitForBytesWritten(500);client.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError('Cannot start the application activation service')
        self.server.newConnection.connect(self.receive)
        return True

    def receive(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection()
            socket.disconnected.connect(socket.deleteLater)
            socket.disconnectFromServer()
            self.activated.emit()

    def release(self):
        self.server.close();self.lock.unlock()
