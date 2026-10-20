import QtQuick
import QtQuick.Window

Item {
    id: effect
    objectName: "coverEffects"
    property bool controllerFocused: false
    property bool suspended: false
    property string identity: ""
    property Item surface: effect
    property real tiltLimit: 18
    property point cursorPoint: Qt.point(width/2,height/2)
    property bool pointerFresh: false
    property real controllerCue: 0
    readonly property var stick: backend.controllerTilt
    readonly property bool stickActive: backend.settings.controller_tilt!==false && (Math.abs(stick[0])>.001 || Math.abs(stick[1])>.001)
    readonly property bool available: Theme.motion && !suspended && visible && !!Window.window && Window.window.visible && Window.window.active
    readonly property bool pointerActive: available && !backend.controllerMode && pointer.hovered && pointerFresh
    readonly property bool hot: available && (pointerActive || backend.controllerMode && controllerFocused)
    readonly property real yaw: !hot ? 0 : pointerActive ? Math.max(-1,Math.min(1,cursorPoint.x/Math.max(1,width)*2-1))*tiltLimit : stickActive ? stick[0]*tiltLimit : -tiltLimit*.32*controllerCue
    readonly property real pitch: !hot ? 0 : pointerActive ? -Math.max(-1,Math.min(1,cursorPoint.y/Math.max(1,height)*2-1))*tiltLimit*.78 : stickActive ? stick[1]*tiltLimit*.78 : tiltLimit*.16*controllerCue
    property real sweep: -.8
    function reset() { shine.stop();lift.stop();controllerCue=0;pointerFresh=false;sweep=-.8 }
    function track(position) {
        var moved=Math.abs(position.x-cursorPoint.x)+Math.abs(position.y-cursorPoint.y)>.5
        cursorPoint=position
        if(moved) pointerFresh=true
    }
    onIdentityChanged: reset()
    onAvailableChanged: if(!available) reset()
    Connections { target: backend; function onInputModeChanged() { effect.reset() } }
    // This input plane never rotates. Only the separate surface receives transforms.
    HoverHandler {
        id: pointer; enabled: effect.available && !backend.controllerMode
        acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
        onPointChanged: if(enabled && hovered) effect.track(point.position)
        onHoveredChanged: { if(hovered && enabled) effect.track(point.position);else effect.pointerFresh=false }
    }
    onHotChanged: {
        if(hot) { shine.restart();if(backend.controllerMode) lift.restart() }
        else { shine.stop();lift.stop();controllerCue=0;sweep=-.8 }
    }
    SequentialAnimation {
        id: lift
        NumberAnimation { target: effect; property: "controllerCue"; to: 1; duration: 100; easing.type: Easing.OutCubic }
        NumberAnimation { target: effect; property: "controllerCue"; to: 0; duration: 220; easing.type: Easing.OutCubic }
    }
    SequentialAnimation {
        id: shine
        PropertyAction { target: effect; property: "sweep"; value: -.8 }
        NumberAnimation { target: effect; property: "sweep"; to: 1.8; duration: 650; easing.type: Easing.OutCubic }
    }
    // One clipped gradient, no shader/layer texture and no repeating animation.
    Item {
        parent: effect.surface; anchors.fill: parent; clip: true; z: 5
        Rectangle {
            objectName: "coverShine"; visible: shine.running && effect.hot
            width: parent.width*.56; height: parent.height*2
            x: effect.sweep*parent.width-width*.5; y: -parent.height*.5; rotation: 24
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "transparent" }
                GradientStop { position: .35; color: "#10fff3d9" }
                GradientStop { position: .5; color: "#60fff7e7" }
                GradientStop { position: .65; color: "#18ffffff" }
                GradientStop { position: 1; color: "transparent" }
            }
        }
        Rectangle { anchors.fill: parent; color: "transparent"; radius: 6; border.width: effect.hot ? 1 : 0; border.color: "#30ffffff" }
    }
}
