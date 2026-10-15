import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: shelf
    property var section: ({items:[],kind:"games"})
    property bool outerMoving: false
    property bool keyboardFocused: false
    property string selectedId: ""
    property bool syncing: false
    property int coverSize: 176
    property int cardGap: 14
    property bool recentPreview: true
    readonly property bool showPreview: section.kind==="recent" && recentPreview && width>=760
    readonly property real tileWidth: section.kind==="tiles" ? Math.round(coverSize*1.34) : section.kind==="recent" ? Math.round(coverSize*.9) : coverSize
    readonly property real scrollTarget: horizontal.running ? horizontal.to : list.contentX
    readonly property int selectionIndex: list.currentIndex
    property var selectedRecord: items.count ? items.get(Math.min(items.count-1,Math.max(0,list.currentIndex))).record : ({})
    signal selectionFocused()
    signal browseRequested(string mode,string value)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal verticalScroll(real delta)
    implicitHeight: section.kind==="tiles" ? 220*coverSize/176 : section.kind==="recent" ? 300*coverSize/176 : 320*coverSize/176
    ListModel { id: items; dynamicRoles: true }
    function sync() {
        var savedId=selectedId;syncing=true
        var rows=section.items || []
        for(var i=0;i<rows.length;i++) {
            var position=-1
            for(var j=i;j<items.count;j++) if(items.get(j).record.id===rows[i].id) { position=j;break }
            if(position<0) items.insert(i,{record:rows[i]})
            else { if(position!==i) items.move(position,i,1);items.set(i,{record:rows[i]}) }
        }
        while(items.count>rows.length) items.remove(items.count-1)
        var previous=rows.findIndex(function(row) { return row.id===savedId })
        list.currentIndex=Math.max(0,previous)
        if(rows.length) selectedId=rows[list.currentIndex].id
        syncing=false
    }
    onSectionChanged: sync()
    Component.onCompleted: sync()
    RowLayout {
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 32; spacing: 8
        Label { text: shelf.section.title || ""; font.pixelSize: 20; font.weight: Font.DemiBold; color: Theme.text }
        Item { Layout.fillWidth: true }
        AppButton { text: "查看全部"; flat: true; onClicked: shelf.browseRequested(shelf.section.target || "all",shelf.section.value || "") }
        IconButton { objectName: "shelfPrevious"; iconName: "arrow-left"; width: 32; height: 32; hint: "向左浏览"; enabled: shelf.scrollTarget>1; onClicked: shelf.move(-1) }
        IconButton { objectName: "shelfNext"; iconName: "arrow-right"; width: 32; height: 32; hint: "向右浏览"; enabled: shelf.scrollTarget+list.width<list.contentWidth-1; onClicked: shelf.move(1) }
    }
    // Section subtitles repeat browsing instructions; keep the cover shelf quiet.
    function selectedGame() { return section.kind==="tiles" ? null : selectedRecord }
    function selectFirst() { horizontal.stop();list.currentIndex=items.count ? 0 : -1;list.positionViewAtBeginning() }
    function activateSelected() { if(section.kind==="tiles") browseRequested(selectedRecord.target,selectedRecord.value);else detailsRequested(selectedRecord) }
    function moveSelection(direction) {
        if(!items.count) return
        var previousIndex=list.currentIndex
        list.currentIndex=Math.max(0,Math.min(items.count-1,list.currentIndex+direction));shelf.selectedId=items.get(list.currentIndex).record.id
        if(previousIndex!==list.currentIndex) backend.navigationMoved()
        var previousX=list.contentX
        list.positionViewAtIndex(list.currentIndex,ListView.Contain)
        var destination=list.contentX;list.contentX=previousX
        if(Math.abs(destination-previousX)>.5) { horizontal.to=destination;horizontal.restart() }
    }
    function move(direction) {
        var step=Math.max(tileWidth+cardGap,Math.floor((list.width+cardGap)/(tileWidth+cardGap))*(tileWidth+cardGap))
        horizontal.to=Math.max(0,Math.min(Math.max(0,list.contentWidth-list.width),scrollTarget+direction*step));horizontal.restart()
    }
    function pageSelection(direction) { moveSelection(direction*Math.max(1,Math.floor(list.width/(tileWidth+cardGap)))) }
    GameTile {
        objectName: "recentHero"; visible: shelf.showPreview && items.count>0
        anchors { left: parent.left; top: parent.top; topMargin: 48; bottom: parent.bottom; bottomMargin: 18 }
        width: Math.min(470*coverSize/176,shelf.width*.45); game: shelf.selectedRecord; featured: true; selected: false; scrolling: shelf.outerMoving
        onDetailsRequested: function(game) { shelf.selectionFocused();shelf.detailsRequested(game) }
        onLaunchRequested: function(game) { shelf.launchRequested(game) }
        onCloudRequested: function(game) { shelf.cloudRequested(game) }
    }
    NumberAnimation { id: horizontal; target: list; property: "contentX"; duration: Theme.motion ? 180 : 0; easing.type: Easing.OutCubic }
    ListView {
        id: list; objectName: "shelf-"+shelf.section.id
        anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 48; bottom: parent.bottom; bottomMargin: 18 }
        anchors.leftMargin: shelf.showPreview ? Math.min(470*coverSize/176,shelf.width*.45)+cardGap : 0
        orientation: ListView.Horizontal; spacing: shelf.cardGap; clip: true; model: items
        reuseItems: true; cacheBuffer: 160; flickDeceleration: 2400; maximumFlickVelocity: 2800
        onCurrentIndexChanged: if(!shelf.syncing && currentIndex>=0 && currentIndex<items.count) shelf.selectedId=items.get(currentIndex).record.id
        delegate: Item {
            required property var record; required property int index
            width: shelf.tileWidth
            height: list.height
            Loader {
                anchors.fill: parent; sourceComponent: shelf.section.kind==="tiles" ? browseTile : gameTile
                Component { id: browseTile; BrowseTile { record: parent.parent.record; selected: shelf.keyboardFocused && parent.parent.index===list.currentIndex; onFocusRequested: { list.currentIndex=parent.parent.index;shelf.selectionFocused() } onClicked: { list.currentIndex=parent.parent.index;shelf.selectionFocused();shelf.browseRequested(record.target,record.value) } } }
                Component { id: gameTile; GameTile {
                    game: parent.parent.record; featured: false; scrolling: shelf.outerMoving || list.moving || horizontal.running
                    selectOnly: shelf.showPreview; selected: parent.parent.index===list.currentIndex && shelf.keyboardFocused
                    onFocusRequested: { list.currentIndex=parent.parent.index;shelf.selectionFocused() }
                    onSelectionRequested: { list.currentIndex=parent.parent.index;shelf.selectionFocused() }
                    onDetailsRequested: function(game) { list.currentIndex=parent.parent.index;shelf.selectionFocused();shelf.detailsRequested(game) }
                    onLaunchRequested: function(game) { shelf.launchRequested(game) }
                    onCloudRequested: function(game) { shelf.cloudRequested(game) }
                } }
            }
        }
        WheelHandler {
            target: null
            onWheel: function(event) {
                if(event.modifiers & Qt.ShiftModifier || event.angleDelta.x) {
                    horizontal.stop();list.contentX=Math.max(0,Math.min(Math.max(0,list.contentWidth-list.width),list.contentX-(event.angleDelta.x || event.angleDelta.y)))
                    event.accepted=true
                }
                else { shelf.verticalScroll(event.pixelDelta.y ? -event.pixelDelta.y : -event.angleDelta.y/120*88);event.accepted=true }
            }
        }
    }
}
