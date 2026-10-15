import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "ExperienceData.js" as Data
Item {
    id: atlas
    property var games: []
    property var game: ({})
    property string groupMode: "category"
    property var graph: Data.atlas(games,groupMode)
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool controllerFocused: false
    readonly property bool compact: height<450
    readonly property var selectedNode: graph.nodes.find(function(n) { return n.game.id===game.id }) || null
    signal selected(string ident)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal removeRequested(var game)
    function limitPan() {
        panX=Math.max(-graph.width*zoom+80,Math.min(map.width-80,panX));panY=Math.max(-graph.height*zoom+80,Math.min(map.height-80,panY))
    }
    function fit() {
        zoom=Math.max(.12,Math.min(1,(map.width-70)/graph.width,(map.height-60)/graph.height))
        panX=(map.width-graph.width*zoom)/2;panY=(map.height-graph.height*zoom)/2
    }
    function startView() {
        zoom=Math.max(.58,Math.min(.85,(map.width-70)/graph.width))
        var node=selectedNode || graph.nodes[0]
        panX=node ? map.width/2-node.x*zoom : 0;panY=node ? map.height/2-node.y*zoom : 0
    }
    function zoomAt(factor,x,y) {
        var next=Math.max(.12,Math.min(2.6,zoom*factor)),ratio=next/zoom
        panX=x-(x-panX)*ratio;panY=y-(y-panY)*ratio;zoom=next;limitPan()
    }
    function reveal() {
        if(!selectedNode) return
        var x=selectedNode.x*zoom+panX,y=selectedNode.y*zoom+panY
        if(x<55 || x>map.width-55 || y<70 || y>map.height-70) { panX=map.width/2-selectedNode.x*zoom;panY=map.height/2-selectedNode.y*zoom }
    }
    function navigate(direction) {
        if(!selectedNode) { if(games.length) selected(games[0].id);return true }
        var best=null,score=Infinity,origin=selectedNode
        graph.nodes.forEach(function(node) {
            var dx=node.x-origin.x,dy=node.y-origin.y,forward=direction==="left" ? -dx : direction==="right" ? dx : direction==="up" ? -dy : dy
            if(forward<=1) return
            var cross=direction==="left" || direction==="right" ? Math.abs(dy) : Math.abs(dx)
            var cost=Math.hypot(dx,dy)+cross*2.6
            if(cost<score) { score=cost;best=node }
        })
        if(!best) return false
        selected(best.game.id);reveal();return true
    }
    function page(direction) { zoomAt(direction>0 ? 1.25 : .8,map.width/2,map.height/2) }
    onGraphChanged: Qt.callLater(startView)
    onGameChanged: { links.requestPaint();Qt.callLater(reveal) }
    onZoomChanged: links.requestPaint()
    onPanXChanged: links.requestPaint()
    onPanYChanged: links.requestPaint()
    Component.onCompleted: Qt.callLater(startView)
    Item {
        id: map; objectName: "atlasMap"; anchors { top: parent.top; bottom: parent.bottom; left: parent.left; right: inspector.left; rightMargin: 16 } clip: true
        onWidthChanged: Qt.callLater(atlas.reveal)
        onHeightChanged: Qt.callLater(atlas.reveal)
        Rectangle { anchors.fill: parent; color: "#101b2e"; radius: 8 }
        Canvas {
            id: stars; anchors.fill: parent; onWidthChanged: requestPaint();onHeightChanged: requestPaint()
            onPaint: {
                var c=getContext("2d");c.clearRect(0,0,width,height)
                for(var y=16;y<height;y+=28) for(var x=16;x<width;x+=28) {
                    var f=(Math.sin(x*12.9898+y*78.233)*43758.5453)%1
                    c.fillStyle=f>.3 ? "#657e9b" : "#2c4059";c.fillRect(x+f*9,y+f*7,f>.3 ? 1.5 : 1,1)
                }
            }
        }
        Canvas {
            id: links; objectName: "atlasRelations"; anchors.fill: parent
            onPaint: {
                var c=getContext("2d");c.clearRect(0,0,width,height)
                atlas.graph.edges.forEach(function(edge) {
                    var ax=edge.a.x*atlas.zoom+atlas.panX,ay=edge.a.y*atlas.zoom+atlas.panY,bx=edge.b.x*atlas.zoom+atlas.panX,by=edge.b.y*atlas.zoom+atlas.panY
                    if(Math.max(ax,bx)<0 || Math.min(ax,bx)>width || Math.max(ay,by)<0 || Math.min(ay,by)>height) return
                    var selected=edge.a.game.id===atlas.game.id || edge.b.game.id===atlas.game.id
                    c.strokeStyle=selected ? Theme.accent : "#46607a";c.globalAlpha=selected ? .9 : .48;c.lineWidth=selected ? 1.8 : 1
                    c.beginPath();c.moveTo(ax,ay);c.lineTo(bx,by);c.stroke()
                });c.globalAlpha=1
            }
        }
        Item {
            x: atlas.panX; y: atlas.panY; scale: atlas.zoom; transformOrigin: Item.TopLeft
            Repeater {
                model: atlas.graph.labels
                Label {
                    required property var modelData
                    x: modelData.x-width/2; y: modelData.y; text: modelData.name+"  "+modelData.count; color: "#b7cde5"; font.pixelSize: 22; font.weight: Font.DemiBold
                }
            }
            Repeater {
                model: atlas.graph.nodes
                Item {
                    id: node
                    required property var modelData
                    x: modelData.x-38; y: modelData.y-50; width: 76; height: 110
                    readonly property bool current: modelData.game.id===atlas.game.id
                    readonly property bool onScreen: (x+width)*atlas.zoom+atlas.panX>0 && x*atlas.zoom+atlas.panX<map.width && (y+height)*atlas.zoom+atlas.panY>0 && y*atlas.zoom+atlas.panY<map.height
                    visible: onScreen
                    Rectangle { anchors.centerIn: parent; width: node.current ? 28 : 13; height: width; radius: width/2; color: node.current ? Theme.accent : "#87a6c8"; visible: atlas.zoom<.42 && !node.current }
                    Loader {
                        anchors.fill: parent; active: node.onScreen && (atlas.zoom>=.42 || node.current)
                        sourceComponent: Item {
                            Rectangle { width: 76; height: 94; radius: 8; color: "#243d59"; border.color: node.current ? Theme.accent : "#6383a7"; border.width: node.current ? 3 : 1
                                Image { anchors.fill: parent; anchors.margins: 5; source: node.modelData.game.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 180 }
                                Label { visible: !node.modelData.game.coverUrl; anchors.fill: parent; anchors.margins: 6; text: node.modelData.game.name; color: "white"; wrapMode: Text.Wrap; font.pixelSize: 13; maximumLineCount: 4; elide: Text.ElideRight }
                            }
                            Label { x: -25; y: 100; width: 126; text: node.modelData.game.name; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 13; color: node.current ? "#ffffff" : "#b9cee5" }
                        }
                    }
                    TapHandler { gesturePolicy: TapHandler.DragThreshold; onTapped: atlas.selected(node.modelData.game.id);onDoubleTapped: atlas.detailsRequested(node.modelData.game) }
                    HoverHandler { cursorShape: Qt.PointingHandCursor; enabled: !backend.controllerMode }
                }
            }
        }
        DragHandler {
            id: drag; objectName: "atlasDrag"; target: null; acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onTranslationChanged: function(delta) { atlas.panX+=delta.x;atlas.panY+=delta.y;atlas.limitPan() }
        }
        WheelHandler { objectName: "atlasZoom"; target: null; onWheel: function(event) { atlas.zoomAt(Math.pow(1.15,event.angleDelta.y/120),event.x,event.y);event.accepted=true } }
        Row {
            anchors.left: parent.left; anchors.bottom: parent.bottom; anchors.margins: 12; spacing: 8
            AppButton { objectName: "atlasZoomOut"; text: "−"; width: 38; onClicked: atlas.zoomAt(.8,map.width/2,map.height/2) }
            AppButton { objectName: "atlasFit"; text: "全览"; width: 60; onClicked: atlas.fit() }
            AppButton { objectName: "atlasZoomIn"; text: "+"; width: 38; onClicked: atlas.zoomAt(1.25,map.width/2,map.height/2) }
            Label { text: Math.round(atlas.zoom*100)+"%"; color: "#b9cee5"; anchors.verticalCenter: parent.verticalCenter }
        }
        Label { visible: atlas.groupMode!=="all"; anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 14; text: "连线：同"+({series:"系列",category:"类别",tags:"标签"}[atlas.groupMode] || ""); color: "#b9cee5"; font.pixelSize: 12 }
    }
    ColumnLayout {
        id: inspector; anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: atlas.width<900 ? 210 : 260; spacing: atlas.compact ? 7 : 12
        Image { Layout.fillWidth: true; Layout.fillHeight: true; Layout.maximumHeight: atlas.compact ? 150 : 330; Layout.minimumHeight: atlas.compact ? 70 : 100; source: atlas.game.coverHighUrl || atlas.game.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 480 }
        Label { text: atlas.game.name || "没有匹配的游戏"; Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: atlas.compact ? 2 : 3; elide: Text.ElideRight; color: Theme.text; font.pixelSize: atlas.compact ? 18 : 21; font.weight: Font.DemiBold }
        Label { text: [atlas.game.series,atlas.game.release_date].filter(Boolean).join("\n"); visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
        Label { visible: !atlas.compact; text: (atlas.game.tags || []).slice(0,5).join("  "); Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight; color: Theme.secondary; font.pixelSize: 12 }
        GameActions {
            Layout.fillWidth: true; Layout.preferredHeight: 42; game: atlas.game
            onLaunchRequested: function(game) { atlas.launchRequested(game) }
            onDetailsRequested: function(game) { atlas.detailsRequested(game) }
            onCloudRequested: function(game) { atlas.cloudRequested(game) }
            onRemoveRequested: function(game) { atlas.removeRequested(game) }
        }
        AppButton { text: atlas.game.favorite ? "★ 已收藏" : "☆ 收藏"; flat: true; enabled: !!atlas.game.id && !backend.busy; onClicked: backend.toggleFavorite(atlas.game.id) }
    }
}
