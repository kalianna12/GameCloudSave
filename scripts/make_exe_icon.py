import struct
from pathlib import Path
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication
app = QApplication([])
root = Path(__file__).resolve().parents[1] / 'ui/icons'
image = QImage(256, 256, QImage.Format_ARGB32)
image.fill(Qt.transparent)
painter = QPainter(image)
QSvgRenderer(str(root / 'app.svg')).render(painter)
painter.end()
data = QByteArray()
buffer = QBuffer(data)
buffer.open(QIODevice.WriteOnly)
assert image.save(buffer, 'PNG')
png = bytes(data)
icon=struct.pack('<HHH',0,1,1) + struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22) + png
target=root/'app.ico'
if not target.exists() or target.read_bytes()!=icon:target.write_bytes(icon)
