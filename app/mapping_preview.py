"""Stable event model; fast capture is independent from frame-paced GUI publication."""
import time
from PySide6.QtCore import QAbstractListModel,QModelIndex,Qt,Signal,Property

class InputHistory(QAbstractListModel):
    countsChanged=Signal()
    def __init__(self,parent=None):super().__init__(parent);self.rows=[];self._counts={};self._total=0
    @Property('QVariantMap',notify=countsChanged)
    def pressCounts(self):return self._counts
    @Property(int,notify=countsChanged)
    def totalPresses(self):return self._total
    def roleNames(self):return {Qt.UserRole+1:b'keyLabel',Qt.UserRole+2:b'pressedDown',Qt.UserRole+3:b'timeLabel'}
    def rowCount(self,parent=QModelIndex()):return 0 if parent.isValid() else len(self.rows)
    def data(self,index,role):
        if not index.isValid() or not 0<=index.row()<len(self.rows):return None
        return self.rows[index.row()].get({Qt.UserRole+1:'key',Qt.UserRole+2:'down',Qt.UserRole+3:'time'}.get(role,''))
    def push(self,events,label):
        if not events:return
        rows=[]
        for event in reversed(events):
            at=event.get('at',time.time())
            rows.append({'key':label(event['token']),'down':event['down'],'time':time.strftime('%H:%M:%S',time.localtime(at))+f'.{int(at*1000)%1000:03d}'})
            if event['down']:self._counts[event['token']]=self._counts.get(event['token'],0)+1;self._total+=1
        self.beginInsertRows(QModelIndex(),0,len(rows)-1);self.rows[0:0]=rows;self.endInsertRows()
        if len(self.rows)>48:
            self.beginRemoveRows(QModelIndex(),48,len(self.rows)-1);del self.rows[48:];self.endRemoveRows()
        self.countsChanged.emit()
    def clear(self):
        if self.rows:self.beginResetModel();self.rows.clear();self.endResetModel()
        self._counts={};self._total=0;self.countsChanged.emit()
