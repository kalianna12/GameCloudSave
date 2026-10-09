import QtQuick
import QtQuick.Controls
Item {
    id: home
    property var sections: []
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
            width: ListView.view.width; height: implicitHeight; section: record; outerMoving: list.moving || vertical.running
            onBrowseRequested: function(mode,value) { home.browseRequested(mode,value) }
            onDetailsRequested: function(game) { home.detailsRequested(game) }
            onLaunchRequested: function(game) { home.launchRequested(game) }
            onCloudRequested: function(game) { home.cloudRequested(game) }
            onVerticalScroll: function(delta) { home.scrollBy(delta) }
        }
        ScrollBar.vertical: ScrollBar {}
    }
}
