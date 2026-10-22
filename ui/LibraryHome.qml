import QtQuick
import QtQuick.Controls
import QtQuick.Window
import "LibraryMetrics.js" as Metrics
FocusScope {
    id: home
    property var sections: []
    property string listObjectName: "libraryHomeList"
    property int coverSize: 176
    property int cardGap: 14
    property bool recentPreview: true
    readonly property bool atTop: !sections.slice(0,focusedSection).some(function(section) { return section.items.length>0 })
    property int focusedSection: 0
    property var rowSelections: ({})
    property int pendingSection: -1
    property bool sectionsDirty: true
    readonly property var sectionLayout: Metrics.sectionLayout(sections,coverSize,list.spacing)
    readonly property var currentFocus: Window.window ? Window.window.activeFocusItem : null
    readonly property bool cardFocus: activeFocus && (currentFocus===home || !!currentFocus && currentFocus.libraryTile===true)
    activeFocusOnTab: true
    Keys.onPressed: function(event) {
        var directions={};directions[Qt.Key_Left]="left";directions[Qt.Key_Right]="right";directions[Qt.Key_Up]="up";directions[Qt.Key_Down]="down"
        if(directions[event.key]) { navigateFocus(directions[event.key]);event.accepted=true }
        else if(event.key===Qt.Key_Return || event.key===Qt.Key_Enter) { activateSelected();event.accepted=true }
    }
    readonly property real scrollMinimum: list.originY
    readonly property real scrollMaximum: list.originY+Math.max(0,sectionLayout.total-list.height)
    function contentPosition() { return list.contentY-list.originY }
    function restorePosition(value) {
        vertical.stop();home.forceActiveFocus();list.forceLayout();list.contentY=list.originY+value
        Qt.callLater(function() { list.forceLayout();list.contentY=Math.max(home.scrollMinimum,Math.min(list.originY+value,home.scrollMaximum));home.ensureSelectionVisible() })
    }
    function resumeFocus() {
        if(currentFocus && currentFocus!==home) currentFocus.focus=false
        home.forceActiveFocus();applyPendingSelection();var shelf=currentShelf();if(shelf) shelf.moveSelection(0);ensureSelectionVisible()
    }
    function ensureSelectionVisible() {
        if(!sections[focusedSection]) return
        var start=list.originY+sectionLayout.offsets[focusedSection],end=start+sectionLayout.heights[focusedSection]
        var destination=vertical.running ? vertical.to : list.contentY
        if(start<destination) destination=start
        else if(end>destination+list.height) destination=end-list.height
        destination=Math.max(scrollMinimum,Math.min(scrollMaximum,destination))
        if(Math.abs(destination-(vertical.running ? vertical.to : list.contentY))>.5) { vertical.duration=Theme.motion ? 100 : 0;vertical.to=destination;vertical.restart() }
    }
    function restoreShelf(index) {
        var shelf=list.itemAtIndex(index),section=sections[index]
        if(!shelf || !section || shelf.section.id!==section.id || shelf.pooled) return
        var saved=rowSelections[section.id]
        if(saved) shelf.restoreSelection(saved.index,saved.x)
        if(index===focusedSection) applyPendingSelection()
    }
    function currentShelf() { var shelf=list.itemAtIndex(focusedSection);return shelf && sections[focusedSection] && shelf.section.id===sections[focusedSection].id ? shelf : null }
    function selectionIndex() {
        var section=sections[focusedSection],saved=section ? rowSelections[section.id] : null
        var shelf=currentShelf()
        return pendingSection!==focusedSection && shelf ? shelf.selectionIndex : saved ? saved.index : 0
    }
    function rememberSelection(index) {
        if(pendingSection===index) return
        var shelf=list.itemAtIndex(index),section=sections[index]
        if(shelf && section && shelf.section.id===section.id && !shelf.syncing) rowSelections[section.id]={index:shelf.selectionIndex,x:shelf.scrollTarget,id:(section.items[shelf.selectionIndex] || {}).id}
    }
    function applyPendingSelection() {
        if(pendingSection<0 || pendingSection!==focusedSection) return
        var shelf=currentShelf(),section=sections[focusedSection]
        if(!shelf || !section) return
        var saved=rowSelections[section.id] || {index:0,x:0}
        shelf.moveSelection(saved.index-shelf.selectionIndex)
        pendingSection=-1
        rememberSelection(focusedSection)
    }
    function rowLeft(section) { return section.kind==="recent" && recentPreview && width>=760 ? Math.min(470*coverSize/176,width*.45)+cardGap : 0 }
    function moveHorizontal(delta) {
        var section=sections[focusedSection]
        if(!section || !section.items.length) return
        var shelf=currentShelf()
        if(shelf && pendingSection!==focusedSection) { shelf.moveSelection(delta);rememberSelection(focusedSection);return }
        var previous=selectionIndex(),next=Math.max(0,Math.min(section.items.length-1,previous+delta))
        var saved=rowSelections[section.id] || {x:0}
        rowSelections[section.id]={index:next,x:saved.x,id:section.items[next].id};pendingSection=focusedSection
        if(next!==previous) backend.navigationMoved()
        applyPendingSelection()
    }
    function pageSelection(direction) {
        var section=sections[focusedSection]
        if(section) moveHorizontal(direction*Math.max(1,Math.floor((width-rowLeft(section))/(Metrics.tileWidth(section,coverSize)+cardGap))))
    }
    function resetSelection() {
        vertical.stop();focusedSection=0;rowSelections={};pendingSection=-1;list.currentIndex=0;list.forceLayout();list.positionViewAtBeginning()
        var shelf=currentShelf();if(shelf) shelf.selectFirst()
    }
    function focusFirst() {
        if(currentFocus && currentFocus!==home) currentFocus.focus=false
        resetSelection();home.forceActiveFocus()
    }
    function selectedGame() { var section=sections[focusedSection];return section && section.kind!=="tiles" && section.kind!=="store" ? section.items[selectionIndex()] || null : null }
    function activateSelected() {
        var section=sections[focusedSection],game=section ? section.items[selectionIndex()] : null
        if(!game) return
        if(section.kind==="store") backend.recommendations.open(game.id)
        else if(section.kind==="tiles") browseRequested(game.target,game.value)
        else launchRequested(game)
    }
    function navigateFocus(direction) {
        if(direction==="left" || direction==="right") {
            var row=currentShelf()
            if(currentFocus && currentFocus!==home) currentFocus.focus=false
            home.forceActiveFocus()
            moveHorizontal(direction==="left" ? -1 : 1)
            return
        }
        var previousSection=focusedSection
        var delta=direction==="up" ? -1 : 1,nextSection=focusedSection+delta
        while(nextSection>=0 && nextSection<sections.length && !sections[nextSection].items.length) nextSection+=delta
        if(nextSection<0 || nextSection>=sections.length) return
        var previousShelf=currentShelf(),previous=sections[previousSection]
        var previousState=previous ? rowSelections[previous.id] || {index:0,x:0} : {index:0,x:0}
        var previousWidth=previous ? Metrics.tileWidth(previous,coverSize) : coverSize
        var sceneX=previousShelf && pendingSection!==previousSection ? previousShelf.selectionSceneX() : home.mapToItem(null,rowLeft(previous || {})+previousState.index*(previousWidth+cardGap)-previousState.x+previousWidth/2,0).x
        rememberSelection(previousSection)
        if(currentFocus && currentFocus!==home) currentFocus.focus=false
        home.forceActiveFocus()
        focusedSection=nextSection
        // Selection lives in the data, not ListView.currentItem. Pinning every
        // rapidly skipped row would synchronously construct its entire shelf.
        var section=sections[focusedSection],tileWidth=Metrics.tileWidth(section,coverSize),saved=rowSelections[section.id] || {x:0}
        var localX=home.mapFromItem(null,sceneX,0).x-rowLeft(section)+saved.x
        var nextIndex=Math.max(0,Math.min(section.items.length-1,Math.round((localX-tileWidth/2)/(tileWidth+cardGap))))
        rowSelections[section.id]={index:nextIndex,x:saved.x,id:(section.items[nextIndex] || {}).id};pendingSection=focusedSection
        ensureSelectionVisible()
        if(previousSection!==focusedSection) backend.navigationMoved()
        applyPendingSelection()
    }
    signal browseRequested(string mode,string value)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal saveSearchRequested(var ids)
    ListModel { id: rows; dynamicRoles: true }
    property var sectionRecords: ({})
    property var sectionSignatures: ({})
    function sync() {
        if(!visible) { sectionsDirty=true;return }
        sectionsDirty=false
        var previousId=focusedSection<rows.count ? rows.get(focusedSection).record.id : ""
        var pendingId=pendingSection>=0 && pendingSection<rows.count ? rows.get(pendingSection).record.id : ""
        var nextRecords={},nextSignatures={}
        for(var i=0;i<sections.length;i++) {
            var position=-1
            for(var j=i;j<rows.count;j++) if(rows.get(j).record.id===sections[i].id) { position=j;break }
            var record=sections[i]
            var signature=record.kind==="store" ? JSON.stringify([record.revision,record.loading,record.message]) : JSON.stringify(record)
            nextRecords[record.id]=record
            nextSignatures[record.id]=signature
            if(position<0) rows.insert(i,{record:record})
            else {
                if(position!==i) rows.move(position,i,1)
                var unchanged=sectionSignatures[record.id]===signature
                if(!unchanged) rows.setProperty(i,"record",record)
            }
        }
        while(rows.count>sections.length) rows.remove(rows.count-1)
        sectionRecords=nextRecords
        sectionSignatures=nextSignatures
        sections.forEach(function(section) {
            var saved=rowSelections[section.id]
            if(!saved) return
            var index=section.items.findIndex(function(game) { return game.id===saved.id })
            rowSelections[section.id]={index:Math.max(0,index),x:saved.x,id:(section.items[Math.max(0,index)] || {}).id}
        })
        var previousIndex=sections.findIndex(function(section) { return section.id===previousId })
        focusedSection=previousIndex>=0 ? previousIndex : Math.max(0,Math.min(focusedSection,rows.count-1))
        if(sections[focusedSection] && !sections[focusedSection].items.length) {
            var nearest=-1
            sections.forEach(function(section,index) { if(section.items.length && (nearest<0 || Math.abs(index-focusedSection)<Math.abs(nearest-focusedSection))) nearest=index })
            if(nearest>=0) focusedSection=nearest
        }
        pendingSection=pendingId && sections[focusedSection] && sections[focusedSection].id===pendingId ? focusedSection : -1
        Qt.callLater(function() { for(var i=0;i<sections.length;i++) home.restoreShelf(i);if(home.cardFocus) home.ensureSelectionVisible() })
    }
    onSectionsChanged: { sectionsDirty=true;if(visible) Qt.callLater(home.sync) }
    onVisibleChanged: { if(visible && sectionsDirty) Qt.callLater(home.sync);else if(!visible) vertical.stop() }
    Component.onCompleted: sync()
    function scrollBy(delta) {
        vertical.duration=Theme.motion ? 110 : 0
        vertical.to=Math.max(scrollMinimum,Math.min(scrollMaximum, (vertical.running ? vertical.to : list.contentY)+delta));vertical.restart()
    }
    NumberAnimation { id: vertical; target: list; property: "contentY"; duration: Theme.motion ? 190 : 0; easing.type: Easing.OutCubic }
    Flickable {
        id: list; objectName: home.listObjectName; anchors.fill: parent
        readonly property int count: rows.count
        property int currentIndex: 0
        property real spacing: 14
        function itemAtIndex(index) { var loader=sectionLoaders.itemAt(index);return loader && loader.status===Loader.Ready ? loader.item : null }
        function forceLayout() { }
        function positionViewAtBeginning() { contentY=0 }
        function positionViewAtIndex(index,mode) { contentY=Math.max(0,Math.min(home.sectionLayout.total-height,home.sectionLayout.offsets[index] || 0)) }
        contentHeight: home.sectionLayout.total
        contentWidth: width;flickableDirection: Flickable.VerticalFlick
        onContentYChanged: home.applyPendingSelection()
        clip: true;boundsBehavior: Flickable.StopAtBounds;flickDeceleration: 2300;maximumFlickVelocity: 3500
        Repeater {
            id: sectionLoaders;model: rows
            delegate: Loader {
                id: sectionLoader
                objectName: "section-loader-"+index
                required property var record
                required property int index
                width: list.width;height: home.sectionLayout.heights[index] || 0;y: home.sectionLayout.offsets[index] || 0
                active: home.visible && y+height>=list.contentY-240 && y<=list.contentY+list.height+240
                // Create only the light shelf skeleton here. Its card loaders
                // stay asynchronous; nesting async incubation can starve rows.
                asynchronous: false
                onLoaded: home.restoreShelf(index)
                sourceComponent: LibraryShelf {
                    section: sectionLoader.record;outerMoving: list.moving || vertical.running
                    coverSize: home.coverSize;cardGap: home.cardGap;recentPreview: home.recentPreview
                    keyboardFocused: home.cardFocus && home.focusedSection===sectionLoader.index
                    onSelectionUpdated: home.rememberSelection(sectionLoader.index)
                    onSelectionFocused: { home.focusedSection=sectionLoader.index;home.pendingSection=-1;home.rememberSelection(sectionLoader.index);home.forceActiveFocus() }
                    onBrowseRequested: function(mode,value) { home.browseRequested(mode,value) }
                    onDetailsRequested: function(game) { home.detailsRequested(game) }
                    onLaunchRequested: function(game) { home.launchRequested(game) }
                    onCloudRequested: function(game) { home.cloudRequested(game) }
                    onSaveSearchRequested: function(ids) { home.saveSearchRequested(ids) }
                    onVerticalScroll: function(delta) { home.scrollBy(delta) }
                }
            }
        }
        ScrollBar.vertical: ScrollBar {}
    }
}
