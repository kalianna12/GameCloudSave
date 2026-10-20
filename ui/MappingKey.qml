import QtQuick
import QtQuick.Controls
Item {
    id: key
    objectName: "mapping-key-"+token
    property string token: ""
    property string label: ""
    property bool selected: false
    property bool pressedLive: false
    property bool surfaceVisible: true
    property bool keyboardCap: false
    property string subLabel: ""
    readonly property bool dropHovered: drop.containsDrag
    readonly property bool controllerSelectable: true
    signal chosen(string token)
    signal assigned(string source,string target)
    implicitWidth: 36; implicitHeight: 32
    activeFocusOnTab: true
    function activate() { chosen(token) }
    Keys.onReturnPressed: activate()
    Rectangle {
        visible: key.surfaceVisible
        anchors.fill: parent; radius: Math.min(8,height/4)
        color: key.pressedLive ? Theme.accent : mouse.pressed || drop.containsDrag ? Theme.hover : key.keyboardCap ? "#24282e" : Theme.surface
        border.color: key.activeFocus || key.selected || drop.containsDrag ? Theme.accent : Theme.outline
        border.width: key.activeFocus || key.selected || drop.containsDrag ? 2 : 1
        Rectangle {
            visible: key.keyboardCap; anchors.fill: parent; anchors.leftMargin: 4; anchors.rightMargin: 4; anchors.topMargin: 3; anchors.bottomMargin: 6
            radius: 4; color: key.pressedLive ? Qt.lighter(Theme.accent,1.1) : "#373c43"; border.color: "#484e56"; border.width: .7
        }
        Label { anchors.centerIn: key.subLabel ? undefined : parent; x: key.subLabel ? 9 : 0; y: key.subLabel ? 3 : 0; width: parent.width-(key.subLabel ? 14 : 4); horizontalAlignment: key.subLabel ? Text.AlignLeft : Text.AlignHCenter; text: key.label; color: key.pressedLive ? Theme.onAccent : key.keyboardCap ? "#e8ecf2" : Theme.text; font.pixelSize: key.subLabel && key.height<36 ? 9 : key.width<32 ? 10 : 12; elide: Text.ElideRight }
        Label { visible: !!key.subLabel; x: 9; anchors.bottom: parent.bottom; anchors.bottomMargin: 6; text: key.subLabel; color: key.pressedLive ? Theme.onAccent : "#929da8"; font.pixelSize: key.height<36 ? 9 : 11 }
    }
    property bool dragging: false
    property double edgeSince: 0
    property int edgeDirection: 0
    onDraggingChanged: if(!dragging) { edgeSince=0;edgeDirection=0 }
    property point origin
    Timer {
        interval: 16;repeat: true;running: key.dragging
        onTriggered: {
            var scroll=key.parent
            while(scroll && scroll.objectName!=="mappingScroll") scroll=scroll.parent
            if(!scroll || !scroll.contentItem) return
            var point=ghost.mapToItem(scroll,ghost.width/2,ghost.height/2),view=scroll.contentItem
            var step=point.y>scroll.height-40 ? 10 : point.y<40 ? -10 : 0
            if(!step) { key.edgeSince=0;key.edgeDirection=0;return }
            var direction=step>0 ? 1 : -1
            if(!key.edgeSince || key.edgeDirection!==direction) { key.edgeSince=Date.now();key.edgeDirection=direction;return }
            if(Date.now()-key.edgeSince<140) return
            if(step) view.contentY=Math.max(0,Math.min(view.contentHeight-view.height,view.contentY+step))
        }
    }
    Rectangle {
        id: ghost; parent: Overlay.overlay; visible: key.dragging; z: 5000
        width: Math.max(42,key.width); height: 34; radius: 6; color: Theme.accent; opacity: .92
        Drag.active: key.dragging; Drag.source: key; Drag.keys: ["gcs-mapping"]
        Drag.hotSpot.x: width/2; Drag.hotSpot.y: height/2
        Label { anchors.centerIn: parent; text: key.label; color: Theme.onAccent }
    }
    MouseArea {
        id: mouse; anchors.fill: parent; hoverEnabled: !backend.controllerMode; preventStealing: true
        onPressed: function(event) { key.forceActiveFocus();key.origin=Qt.point(event.x,event.y) }
        onPositionChanged: function(event) {
            if(!pressed) return
            if(!key.dragging && Math.abs(event.x-key.origin.x)+Math.abs(event.y-key.origin.y)>8) key.dragging=true
            if(key.dragging) { var point=key.mapToItem(ghost.parent,event.x,event.y);ghost.x=point.x-ghost.width/2;ghost.y=point.y-ghost.height/2 }
        }
        onReleased: { if(key.dragging) ghost.Drag.drop();else key.activate();key.dragging=false;backend.mapping.clearDropHint("") }
        onCanceled: { key.dragging=false;backend.mapping.clearDropHint("") }
    }
    DropArea {
        id: drop; anchors.fill: parent; keys: ["gcs-mapping"]
        onEntered: function(event) {
            event.accepted=event.source && event.source!==key && backend.mapping.canDrop(event.source.token,key.token)
            if(event.accepted) backend.mapping.hoverDrop(event.source.token,key.token)
        }
        onExited: backend.mapping.clearDropHint(key.token)
        onDropped: function(event) { if(event.source && event.source.token && event.source!==key && backend.mapping.canDrop(event.source.token,key.token)) { key.assigned(event.source.token,key.token);event.acceptProposedAction() };backend.mapping.clearDropHint(key.token) }
    }
    Rectangle {
        visible: drop.containsDrag && backend.mapping.dropTarget===key.token;z: 10000
        anchors.horizontalCenter: parent.horizontalCenter;y: key.height+5;width: hint.implicitWidth+16;height: 25;radius: 5;color: Theme.accent
        Label { id: hint;anchors.centerIn: parent;text: "绑定到 "+key.label;color: Theme.onAccent;font.pixelSize: 11 }
    }
    ToolTip.visible: mouse.containsMouse && !key.dragging && !backend.controllerMode && !backend.mapping.dropTarget
    ToolTip.text: key.token.startsWith("K:") ? backend.mapping.label(key.token) : key.label; ToolTip.delay: 500
}
