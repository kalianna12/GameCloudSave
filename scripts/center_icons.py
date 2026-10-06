"""Normalize each SVG's visible bounds, rather than trusting its artboard."""
from pathlib import Path
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage,QPainter
from PySide6.QtSvg import QSvgRenderer
directory=Path(__file__).resolve().parents[1]/'ui/icons'
for file in directory.glob('*.svg'):
    if file.stem=='app': continue
    source=file.read_text(encoding='utf-8')
    source=re.sub(r'viewBox="[^"]+"','viewBox="0 0 24 24"',source)
    image=QImage(240,240,QImage.Format_ARGB32); image.fill(Qt.transparent)
    painter=QPainter(image); QSvgRenderer(source.encode()).render(painter); painter.end()
    points=[(x,y) for y in range(240) for x in range(240) if image.pixelColor(x,y).alpha()>32]
    if not points: continue
    left=min(p[0] for p in points); right=max(p[0] for p in points)
    top=min(p[1] for p in points); bottom=max(p[1] for p in points)
    dx=((left+right+1)/2-120)/10; dy=((top+bottom+1)/2-120)/10
    source=source.replace('viewBox="0 0 24 24"',f'viewBox="{dx:.3f} {dy:.3f} 24 24"')
    file.write_text(source,encoding='utf-8')
