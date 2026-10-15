import QtQuick
import QtQuick.Controls
import QtQuick.Window
FocusScope {
    id: home
    property var sections: []
    property int coverSize: 176
    property int cardGap: 14
    property bool recentPreview: true
    readonly property bool atTop: focusedSection===0
    property int focusedSection: 0
    readonly property var currentFocus: Window.window ? Window.window.activeFocusItem : null
    readonly property bool cardFocus: activeFocus && (currentFocus===home || !!currentFocus && currentFocus.libraryTile===true)
    activeFocusOnTab: true
    Keys.onPressed: function(event) {
        var directions={};directions[Qt.Key_Left]="left";directions[Qt.Key_Right]="right";directions[Qt.Key_Up]="up";directions[Qt.Key_Down]="down"
        if(directions[event.key]) { navigateFocus(directions[event.key]);event.accepted=true }
        else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter) { activateSelected();event.accepted=true }
    }
    function contentPosition() { return list.contentY }
    function restorePosition(value) {
        vertical.stop();home.forceActiveFocus();list.forceLayout();list.contentY=value
        Qt.callLater(function() { list.forceLayout();list.contentY=Math.max(list.originY,Math.min(value,Math.max(list.originY,list.contentHeight-list.height))) })
    }
    function currentShelf() { return list.itemAtIndex(focusedSection) }
    function resetSelection() {
        vertical.stop();focusedSection=0;list.currentIndex=0;list.forceLayout();list.positionViewAtBeginning()
        var shelf=currentShelf();if(shelf) shelf.selectFirst()
    }
    function focusFirst() {
        if(currentFocus && currentFocus!==home) currentFocus.focus=false
        resetSelection();home.forceActiveFocus()
    }
    function selectedGame() { var shelf=currentShelf();return shelf ? shelf.selectedGame() : null }
    function activateSelected() { var shelf=currentShelf();if(shelf) shelf.activateSelected() }
    function navigateFocus(direction) {
        var previousSection=focusedSection
        if(currentFocus && currentFocus!==home) currentFocus.focus=false
        home.forceActiveFocus()
        if(direction==="up" || direction==="down") focusedSection=Math.max(0,Math.min(rows.count-1,focusedSection+(direction==="up" ? -1 : 1)))
        list.forceLayout()
        var previousY=list.contentY
        vertical.stop();list.currentIndex=focusedSection;list.positionViewAtIndex(focusedSection,ListView.Contain)
        var destination=list.contentY
        list.contentY=previousY
        if(Math.abs(destination-previousY)>.5) { vertical.duration=Theme.motion ? 190 : 0;vertical.to=destination;vertical.restart() }
        else list.contentY=destination
        if(previousSection!==focusedSection) backend.navigationMoved()
        var shelf=home.currentShelf()
        if(shelf && (direction==="left" || direction==="right")) shelf.moveSelection(direction==="left" ? -1 : 1)
    }
    signal browseRequested(string mode,string value)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    ListModel { id: rows; dynamicRoles: true }
    function sync() {
        for(var i=0;i<sections.length;i++) {
            var position=-1
            for(var j=i;j<rows.count;j++) if(rows.get(j).record.id===sections[i].id) { position=j;break }
            if(position<0) rows.insert(i,{record:sections[i]})
            else { if(position!==i) rows.move(position,i,1);rows.set(i,{record:sections[i]}) }
        }
        while(rows.count>sections.length) rows.remove(rows.count-1)
    }
    onSectionsChanged: sync()
    Component.onCompleted: sync()
    function scrollBy(delta) {
        vertical.duration=Theme.motion ? 110 : 0
        vertical.to=Math.max(0,Math.min(Math.max(0,list.contentHeight-list.height), (vertical.running ? vertical.to : list.contentY)+delta));vertical.restart()
    }
    NumberAnimation { id: vertical; target: list; property: "contentY"; duration: Theme.motion ? 190 : 0; easing.type: Easing.OutCubic }
    ListView {
        id: list; objectName: "libraryHomeList"; anchors.fill: parent; model: rows
        clip: true; reuseItems: true; cacheBuffer: 240; spacing: 14; flickDeceleration: 2300; maximumFlickVelocity: 3500
        delegate: LibraryShelf {
            required property var record
            required property int index
            width: ListView.view.width; height: implicitHeight; section: record; outerMoving: list.moving || vertical.running
            coverSize: home.coverSize; cardGap: home.cardGap; recentPreview: home.recentPreview
            keyboardFocused: home.cardFocus && home.focusedSection===index
            onSelectionFocused: { home.focusedSection=index;home.forceActiveFocus() }
            onBrowseRequested: function(mode,value) { home.browseRequested(mode,value) }
            onDetailsRequested: function(game) { home.detailsRequested(game) }
            onLaunchRequested: function(game) { home.launchRequested(game) }
            onCloudRequested: function(game) { home.cloudRequested(game) }
            onVerticalScroll: function(delta) { home.scrollBy(delta) }
        }
        ScrollBar.vertical: ScrollBar {}
    }
}
