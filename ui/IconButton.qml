import QtQuick
import QtQuick.Window
import QtQuick.Controls
AbstractButton {
    id: control
    property string iconName: "play"
    property string hint: ""
    property bool accent: false
    property string transferState: "idle"
    property bool loading: transferState === "saving" || transferState === "uploading"
    implicitWidth: 42
    implicitHeight: 42
    padding: 0
    hoverEnabled: !backend.controllerMode
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
    ToolTip.visible: hovered
    ToolTip.text: hint
    ToolTip.delay: 350
    Accessible.name: hint
    background: Rectangle {
        radius: 5
        x: 0; y: 0; width: control.width; height: control.height
        color: control.transferState === "success" ? "#34502a" : control.transferState === "failed" ? "#56302d" : control.accent ? (control.hovered ? Qt.lighter(Theme.accent,1.12) : Theme.accent) : (control.hovered ? Theme.hover : "transparent")
        border.color: control.activeFocus ? Theme.secondary : "transparent"
    }
    contentItem: Item {
        x: 0; y: 0; width: control.width; height: control.height
        Image {
            id: glyph
            anchors.centerIn: parent
            width: 20; height: 20
            visible: !control.loading
            source: backend.iconSource(control.transferState === "success" ? "success" : control.transferState === "failed" ? "failed" : control.iconName,(control.transferState === "success" || control.transferState === "failed" ? "#ffffff" : control.accent ? Theme.onAccent : Theme.text).toString())
            sourceSize: Qt.size(Math.ceil(width*Screen.devicePixelRatio), Math.ceil(height*Screen.devicePixelRatio))
            opacity: control.enabled ? 1 : 0.4
        }
        BusyIndicator { anchors.centerIn: parent; width: 30; height: 30; running: control.loading; visible: running }
    }
}
