"""A small idle incubation budget also works for hidden secondary windows."""
from PySide6.QtCore import QTimer,Qt
from PySide6.QtQml import QQmlIncubationController
import shiboken6

class IdleIncubator(QQmlIncubationController):
    def __init__(self,engine):
        super().__init__();self.timer=QTimer(engine);self.timer.setInterval(4);self.timer.setTimerType(Qt.PreciseTimer);self.timer.timeout.connect(self.pump)
    def incubatingObjectCountChanged(self,count):
        if not shiboken6.isValid(self.timer):return
        if count:self.timer.start()
        else:self.timer.stop()
    def pump(self):self.incubateFor(2)

def install_incubator(engine):
    engine._idle_incubator=IdleIncubator(engine)
    engine.setIncubationController(engine._idle_incubator)
