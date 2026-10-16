import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ExperienceData.js" as Data
Item {
    id: atlas
    property var games: []
    property var game: ({})
    property string groupMode: "category"
    property string order: "release_asc"
    property var graph: Data.atlas(games,groupMode,order)
    readonly property string layoutIdentity: graph.nodes.map(function(n) { return n.game.id+":"+n.x+":"+n.y }).join("|")
    property real zoom: 1
    property real panX: 0
    property real panY: 0
    property bool controllerFocused: false
    property bool launching: false
    property real selectionGlow: 0
    property real luckyProgress: 1
    readonly property bool lucky: luckyAnimation.running
    property string lastSelectedId: ""
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
        cameraX.stop();cameraY.stop()
        zoom=Math.max(.12,Math.min(1,(map.width-70)/graph.width,(map.height-60)/graph.height))
        panX=(map.width-graph.width*zoom)/2;panY=(map.height-graph.height*zoom)/2
    }
    function startView() {
        cameraX.stop();cameraY.stop()
        var node=selectedNode || graph.nodes[0]
        var cluster=node ? graph.labels.find(function(g) { return g.name===node.group }) : null
        zoom=cluster ? Math.max(.55,Math.min(.9,(map.width-70)/cluster.width,(map.height-60)/cluster.height)) : .9
        panX=cluster ? (map.width-cluster.width*zoom)/2-cluster.x*zoom : 0;panY=cluster ? (map.height-cluster.height*zoom)/2-cluster.y*zoom : 0
    }
    function zoomAt(factor,x,y) {
        cameraX.stop();cameraY.stop()
        var next=Math.max(.12,Math.min(2.6,zoom*factor)),ratio=next/zoom
        panX=x-(x-panX)*ratio;panY=y-(y-panY)*ratio;zoom=next;limitPan()
    }
    function reveal() {
        if(!selectedNode) return
        var x=selectedNode.x*zoom+panX,y=selectedNode.y*zoom+panY
        if(x<80 || x>map.width-80 || y<100 || y>map.height-105) panTo(map.width/2-selectedNode.x*zoom,map.height/2-selectedNode.y*zoom)
    }
    function panTo(x,y) { cameraX.stop();cameraY.stop();if(Theme.motion && visible && Window.window && Window.window.active) { cameraX.to=x;cameraY.to=y;cameraX.restart();cameraY.restart() } else { panX=x;panY=y } }
    function firstGame() { return graph.nodes.length ? graph.nodes[0].game : null }
    function celebrate() { if(!Theme.motion || !selectedNode) return;panTo(map.width/2-selectedNode.x*zoom,map.height/2-selectedNode.y*zoom);luckyAnimation.restart() }
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
    function zoomController(direction) { zoomAt(direction>0 ? 1.09 : 1/1.09,map.width/2,map.height/2) }
    onLayoutIdentityChanged: Qt.callLater(startView)
    onGraphChanged: links.requestPaint()
    onGameChanged: { links.requestPaint();Qt.callLater(reveal);if(game.id!==lastSelectedId) { lastSelectedId=game.id || "";if(Theme.motion) selectedAnimation.restart() } }
    onZoomChanged: links.requestPaint()
    onPanXChanged: links.requestPaint()
    onPanYChanged: links.requestPaint()
    Component.onCompleted: Qt.callLater(startView)
    NumberAnimation { id: cameraX; target: atlas; property: "panX"; duration: 260; easing.type: Easing.OutCubic }
    NumberAnimation { id: cameraY; target: atlas; property: "panY"; duration: 260; easing.type: Easing.OutCubic }
    NumberAnimation { id: selectedAnimation; target: atlas; property: "selectionGlow"; from: 1; to: 0; duration: 420 }
    NumberAnimation { id: luckyAnimation; target: atlas; property: "luckyProgress"; from: 0; to: 1; duration: 620; easing.type: Easing.OutCubic }
    onSelectionGlowChanged: links.requestPaint()
    onVisibleChanged: if(!visible) { cameraX.stop();cameraY.stop();selectedAnimation.stop();luckyAnimation.stop() }
    Connections { target: Theme; function onMotionChanged() { if(!Theme.motion) { cameraX.stop();cameraY.stop();selectedAnimation.stop();luckyAnimation.stop();atlas.selectionGlow=0;atlas.luckyProgress=1 } } }
    Connections { target: atlas.Window.window; function onActiveChanged() { if(!atlas.Window.window.active) { cameraX.stop();cameraY.stop();selectedAnimation.stop();luckyAnimation.stop() } } }
    Item {
        id: map; objectName: "atlasMap"; anchors { top: parent.top; bottom: parent.bottom; left: parent.left; right: inspector.left; rightMargin: 16 } clip: true
        onWidthChanged: Qt.callLater(atlas.reveal)
        onHeightChanged: Qt.callLater(atlas.reveal)
        Rectangle { anchors.fill: parent; color: "#101b2e"; radius: 8 }
        AtlasSky { anchors.fill: parent; offsetX: atlas.panX; offsetY: atlas.panY; suspended: atlas.launching }
        Canvas {
            id: links; objectName: "atlasRelations"; anchors.fill: parent
            onPaint: {
                var c=getContext("2d");c.clearRect(0,0,width,height)
                atlas.graph.edges.forEach(function(edge) {
                    var ax=edge.a.x*atlas.zoom+atlas.panX,ay=edge.a.y*atlas.zoom+atlas.panY,bx=edge.b.x*atlas.zoom+atlas.panX,by=edge.b.y*atlas.zoom+atlas.panY
                    if(Math.max(ax,bx)<0 || Math.min(ax,bx)>width || Math.max(ay,by)<0 || Math.min(ay,by)>height) return
                    var selected=edge.a.game.id===atlas.game.id || edge.b.game.id===atlas.game.id
                    if(!selected && edge.a.group!==edge.b.group) return
                    c.strokeStyle=selected ? "#ffe2a0" : edge.color;c.globalAlpha=selected ? .85 : .24;c.lineWidth=selected ? 1.8+atlas.selectionGlow : 1
                    c.beginPath();c.moveTo(ax,ay);c.lineTo(bx,by);c.stroke()
                });c.globalAlpha=1
            }
        }
        Item {
            x: atlas.panX; y: atlas.panY; scale: atlas.zoom; transformOrigin: Item.TopLeft
            Repeater {
                model: atlas.graph.labels
                Item {
                    required property var modelData
                    readonly property color clusterColor: modelData.color
                    x: modelData.x; y: modelData.y; width: modelData.width; height: modelData.height
                    Canvas {
                        id: clusterCloud; anchors.centerIn: parent; width: Math.min(640,parent.width); height: Math.min(640,parent.height)
                        transform: Scale { origin.x: clusterCloud.width/2; origin.y: clusterCloud.height/2; xScale: clusterCloud.parent.width/clusterCloud.width; yScale: clusterCloud.parent.height/clusterCloud.height }
                        onPaint: { var c=getContext("2d"),r=Math.max(width,height)*.6,g=c.createRadialGradient(width/2,height/2,0,width/2,height/2,r);g.addColorStop(0,Qt.rgba(parent.clusterColor.r,parent.clusterColor.g,parent.clusterColor.b,.12));g.addColorStop(1,"transparent");c.clearRect(0,0,width,height);c.fillStyle=g;c.fillRect(0,0,width,height) }
                    }
                    Label { x: 24; y: 16; width: parent.width-48; height: 30; text: modelData.name+"  "+modelData.count; color: modelData.color; font.pixelSize: 18; font.weight: Font.DemiBold; elide: Text.ElideRight }
                }
            }
            Repeater {
                model: atlas.graph.nodes
                Item {
                    id: node
                    required property var modelData
                    objectName: "atlasNode-"+modelData.game.id
                    x: modelData.x-72; y: modelData.y-86; width: 144; height: 174
                    readonly property bool current: modelData.game.id===atlas.game.id
                    readonly property bool onScreen: (x+width)*atlas.zoom+atlas.panX>0 && x*atlas.zoom+atlas.panX<map.width && (y+height)*atlas.zoom+atlas.panY>0 && y*atlas.zoom+atlas.panY<map.height
                    visible: onScreen
                    Rectangle { anchors.centerIn: parent; width: 13; height: width; radius: width/2; color: node.modelData.color; visible: atlas.zoom<.34 && !node.current }
                    Loader {
                        anchors.fill: parent; active: node.onScreen && (atlas.zoom>=.34 || node.current)
                        sourceComponent: Item {
                            Rectangle { visible: node.current && atlas.controllerFocused; x: 21; y: -6; width: 102; height: 124; radius: 12; color: Theme.selection; border.color: Theme.accent; border.width: 1; opacity: .5+atlas.selectionGlow*.5 }
                            Rectangle { x: 28; width: 88; height: 112; radius: 8; color: "#243d59"; border.color: node.modelData.color; border.width: 2
                                scale: nodeHover.hovered && Theme.motion ? 1.04 : 1;Behavior on scale { NumberAnimation { duration: Theme.motion ? 140 : 0 } }
                                Image { anchors.fill: parent; anchors.margins: 5; source: node.modelData.game.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 180 }
                                SelectionFrame { objectName: "atlasFocusRing"; selected: node.current && atlas.controllerFocused; radius: 8 }
                                Label { visible: !node.modelData.game.coverUrl; anchors.fill: parent; anchors.margins: 6; text: node.modelData.game.name; color: "white"; wrapMode: Text.Wrap; font.pixelSize: 13; maximumLineCount: 4; elide: Text.ElideRight }
                            }
                            TitleLabel { objectName: "atlasNodeTitle"; x: 0; y: 121; width: 144; height: 32; text: node.modelData.game.name; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12; color: node.current ? "#fff0cd" : "#d2deed"; scrolling: drag.active }
                            Label { y: 157; width: 144; height: 14; text: node.modelData.game.release_date || "日期未知"; color: node.modelData.color; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 10 }
                        }
                    }
                    Rectangle { visible: node.current && atlas.lucky; x: 72-width/2; y: 54-height/2; width: 90+atlas.luckyProgress*110; height: width; radius: width/2; color: "transparent"; border.color: "#ffe2a0"; border.width: 3; opacity: 1-atlas.luckyProgress }
                    Repeater { model: node.current && atlas.lucky ? 8 : 0; Rectangle { required property int index; readonly property real angle: index*Math.PI/4; x: 72+Math.cos(angle)*(60+atlas.luckyProgress*65)-2; y: 54+Math.sin(angle)*(60+atlas.luckyProgress*65)-2; width: 4; height: 4; rotation: 45; color: "#ffdfa0"; opacity: 1-atlas.luckyProgress } }
                    TapHandler { gesturePolicy: TapHandler.DragThreshold; onTapped: atlas.selected(node.modelData.game.id);onDoubleTapped: atlas.detailsRequested(node.modelData.game) }
                    HoverHandler { id: nodeHover; cursorShape: Qt.PointingHandCursor; enabled: !backend.controllerMode }
                }
            }
        }
        DragHandler {
            id: drag; objectName: "atlasDrag"; target: null; acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onActiveChanged: if(active) { cameraX.stop();cameraY.stop() }
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
        Label { visible: atlas.groupMode!=="all"; anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 14; text: "连线：同"+({series:"系列",category:"类别",tags:"标签",year:"发行年份"}[atlas.groupMode] || ""); color: "#b9cee5"; font.pixelSize: 12 }
    }
    ColumnLayout {
        id: inspector; anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom; width: atlas.width<900 ? 210 : 260; spacing: atlas.compact ? 7 : 12
        Label { visible: atlas.lucky; text: "✦ 幸运之选"; color: "#ffe2a0"; font.pixelSize: 18; font.weight: Font.DemiBold }
        Label { visible: !!atlas.selectedNode && !atlas.lucky; text: atlas.selectedNode ? atlas.selectedNode.group : ""; color: atlas.selectedNode ? atlas.selectedNode.color : Theme.secondary; font.pixelSize: 14 }
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
