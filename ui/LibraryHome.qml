import QtQuick
import QtQuick.Controls
FocusScope {
    id: home
    property var sections: []
    property int focusedSection: 0
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
    function selectedGame() { var shelf=currentShelf();return shelf ? shelf.selectedGame() : null }
    function activateSelected() { var shelf=currentShelf();if(shelf) shelf.activateSelected() }
    function navigateFocus(direction) {
        home.forceActiveFocus()
        if(direction==="up" || direction==="down") focusedSection=Math.max(0,Math.min(rows.count-1,focusedSection+(direction==="up" ? -1 : 1)))
        list.currentIndex=focusedSection;list.positionViewAtIndex(focusedSection,ListView.Contain)
        Qt.callLater(function() { var shelf=home.currentShelf();if(shelf) { shelf.keyboardFocused=true;if(direction==="left" || direction==="right") shelf.moveSelection(direction==="left" ? -1 : 1) } })
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
        vertical.to=Math.max(0,Math.min(Math.max(0,list.contentHeight-list.height), (vertical.running ? vertical.to : list.contentY)+delta));vertical.restart()
    }
    NumberAnimation { id: vertical; target: list; property: "contentY"; duration: Theme.motion ? 110 : 0; easing.type: Easing.OutCubic }
    ListView {
        id: list; objectName: "libraryHomeList"; anchors.fill: parent; model: rows
        clip: true; reuseItems: true; cacheBuffer: 240; spacing: 14; flickDeceleration: 2300; maximumFlickVelocity: 3500
        delegate: LibraryShelf {
            required property var record
            required property int index
            width: ListView.view.width; height: implicitHeight; section: record; outerMoving: list.moving || vertical.running
            keyboardFocused: home.activeFocus && home.focusedSection===index
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
