import QtQuick
import QtQuick.Window

Item {
    id: effect
    objectName: "coverEffects"
    property bool controllerFocused: false
    property bool suspended: false
    property real tiltLimit: 6
    readonly property bool available: Theme.motion && !suspended && visible && !!Window.window && Window.window.active
    readonly property bool hot: available && (pointer.hovered || controllerFocused)
    readonly property real yaw: !hot ? 0 : pointer.hovered ? Math.max(-1,Math.min(1,pointer.point.position.x/Math.max(1,width)*2-1))*tiltLimit : -tiltLimit*.3
    readonly property real pitch: !hot ? 0 : pointer.hovered ? -Math.max(-1,Math.min(1,pointer.point.position.y/Math.max(1,height)*2-1))*tiltLimit : tiltLimit*.18
    property real sweep: -.8
    HoverHandler { id: pointer; enabled: effect.available && !backend.controllerMode }
    onHotChanged: {
        if(hot) shine.restart()
        else { shine.stop();sweep=-.8 }
    }
    SequentialAnimation {
        id: shine
        PropertyAction { target: effect; property: "sweep"; value: -.8 }
        NumberAnimation { target: effect; property: "sweep"; to: 1.8; duration: 650; easing.type: Easing.OutCubic }
    }
    // One clipped gradient, no shader/layer texture and no repeating animation.
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
