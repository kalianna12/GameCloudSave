import QtQuick
import QtQuick.Controls
Button {
    id: control
    property string iconName: "play"
    property string hint: ""
    property bool accent: false
    implicitWidth: 40
    implicitHeight: 36
    padding: 0
    ToolTip.visible: hovered
    ToolTip.text: hint
    ToolTip.delay: 350
    Accessible.name: hint
    background: Rectangle {
        radius: 8
        color: control.accent ? (control.hovered ? "#a5f570" : "#8ce34f") : (control.hovered ? "#354039" : "#252e29")
        border.color: control.activeFocus ? "#b5fa85" : "transparent"
    }
    contentItem: Item {
        Image {
            anchors.centerIn: parent
            width: 19; height: 19
            source: "icons/" + control.iconName + ".svg"
            sourceSize: Qt.size(19, 19)
            opacity: control.enabled ? 1 : 0.4
        }
    }
}
