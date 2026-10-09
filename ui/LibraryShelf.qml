import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: shelf
    property var section: ({items:[],kind:"games"})
    property bool outerMoving: false
    signal browseRequested(string mode,string value)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal verticalScroll(real delta)
    implicitHeight: section.kind==="tiles" ? 220 : section.kind==="recent" ? 318 : 338
    ListModel { id: items; dynamicRoles: true }
    function sync() {
        var rows=section.items || []
        for(var i=0;i<rows.length;i++) {
            var position=-1
            for(var j=i;j<items.count;j++) if(items.get(j).record.id===rows[i].id) { position=j;break }
            if(position<0) items.insert(i,{record:rows[i]})
            else { if(position!==i) items.move(position,i,1);items.set(i,{record:rows[i]}) }
        }
        while(items.count>rows.length) items.remove(items.count-1)
    }
    onSectionChanged: sync()
    Component.onCompleted: sync()
    RowLayout {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 32; spacing: 8
        Label { text: shelf.section.title || ""; font.pixelSize: 22; font.bold: true; color: Theme.text }
        Item { Layout.fillWidth: true }
        AppButton { text: "查看全部"; onClicked: shelf.browseRequested(shelf.section.target || "all",shelf.section.value || "") }
        IconButton { iconName: "arrow-left"; width: 32; height: 32; hint: "向左浏览"; enabled: list.contentX>1; onClicked: shelf.move(-1) }
        IconButton { iconName: "arrow-right"; width: 32; height: 32; hint: "向右浏览"; enabled: list.contentX+list.width<list.contentWidth-1; onClicked: shelf.move(1) }
    }
    Label { y: 37; width: parent.width; text: shelf.section.subtitle || ""; color: Theme.secondary; font.pixelSize: 11; elide: Text.ElideRight }
    function move(direction) { horizontal.to=Math.max(0,Math.min(list.contentWidth-list.width,list.contentX+direction*list.width*.8));horizontal.restart() }
    NumberAnimation { id: horizontal; target: list; property: "contentX"; duration: Theme.motion ? 180 : 0; easing.type: Easing.OutCubic }
    ListView {
        id: list; objectName: "shelf-"+shelf.section.id
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: shelf.section.subtitle ? 66 : 48; bottom: parent.bottom; bottomMargin: 18 }
        orientation: ListView.Horizontal; spacing: 14; clip: true; model: items
        reuseItems: true; cacheBuffer: 160; flickDeceleration: 2400; maximumFlickVelocity: 2800
        delegate: Item {
            required property var record; required property int index
            width: shelf.section.kind==="tiles" ? 236 : shelf.section.kind==="recent" && index===0 ? Math.min(470,list.width*.55) : shelf.section.kind==="recent" ? 158 : 176
            height: list.height
            Loader {
                anchors.fill: parent; sourceComponent: shelf.section.kind==="tiles" ? browseTile : gameTile
                Component { id: browseTile; BrowseTile { record: parent.parent.record; onClicked: shelf.browseRequested(record.target,record.value) } }
                Component { id: gameTile; GameTile {
                    game: parent.parent.record; featured: shelf.section.kind==="recent" && parent.parent.index===0; scrolling: shelf.outerMoving || list.moving
                    onDetailsRequested: function(game) { shelf.detailsRequested(game) }
                    onLaunchRequested: function(game) { shelf.launchRequested(game) }
                    onCloudRequested: function(game) { shelf.cloudRequested(game) }
                } }
            }
        }
        WheelHandler {
            target: null
            onWheel: function(event) {
                if(event.modifiers & Qt.ShiftModifier || event.angleDelta.x) { list.contentX=Math.max(0,Math.min(Math.max(0,list.contentWidth-list.width),list.contentX-(event.angleDelta.x || event.angleDelta.y)));event.accepted=true }
                else { shelf.verticalScroll(event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y/120*88);event.accepted=true }
            }
        }
    }
}
