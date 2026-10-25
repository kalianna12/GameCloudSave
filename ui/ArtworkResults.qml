import QtQuick
import QtQuick.Controls
GridView {
    id: grid
    property string targetKey: ""
    property string kind: "cover"
    property bool completion: false
    signal chosen(string ident,string kind)
    clip: true
    cellWidth: width/Math.max(1,Math.floor(width/190)); cellHeight: completion ? 300 : 240
    ListModel { id: stable; dynamicRoles: true }
    model: stable
    function sync() {
        var rows=backend.coverSearchTarget===targetKey ? backend.coverResults : []
        for(var i=0;i<rows.length;i++) {
            var index=-1
            for(var j=i;j<stable.count;j++) if(stable.get(j).candidate.id===rows[i].id) { index=j;break }
            if(index<0) stable.insert(i,{candidate:rows[i]})
            else { if(index!==i) stable.move(index,i,1);stable.setProperty(i,"candidate",rows[i]) }
        }
        if(stable.count>rows.length) stable.remove(rows.length,stable.count-rows.length)
    }
    Component.onCompleted: sync()
    onTargetKeyChanged: Qt.callLater(sync)
    onVisibleChanged: if(visible) Qt.callLater(sync)
    Connections { target: backend; function onChanged() { if(grid.visible) grid.sync() } }
    delegate: ArtworkCandidate {
        required property var candidate
        width: grid.cellWidth; height: grid.cellHeight; record: candidate; kind: grid.kind; completion: grid.completion
        onChosen: function(kind) { grid.chosen(candidate.id,kind) }
    }
    ScrollBar.vertical: ScrollBar {}
    Label { visible: grid.count===0; anchors.centerIn: parent; width: Math.max(0,parent.width-30); text: backend.coverSearchTarget===grid.targetKey && backend.artworkSearching ? "正在搜索…" : backend.coverSearchTarget===grid.targetKey && backend.artworkError ? backend.artworkError : "输入名称并搜索，候选图片会显示在这里"; color: Theme.secondary; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
}
