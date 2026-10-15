import QtQuick
import QtQuick.Controls
AbstractButton {
    id: choice
    property var colors: ({})
    property bool selected: false
    implicitWidth: 170; implicitHeight: 120
    hoverEnabled: !backend.controllerMode
    Accessible.name: (colors.name || "")+(selected ? "，当前主题" : "")
    background: Rectangle {
        radius: Theme.radius; color: Theme.surface
        border.color: choice.selected || choice.activeFocus ? Theme.accent : choice.hovered ? Theme.secondary : Theme.outline
        border.width: choice.selected || choice.activeFocus ? 2 : 1
    }
    contentItem: Item {
        Rectangle {
            x: 9; y: 9; width: parent.width-18; height: 70
            color: choice.colors.background || Theme.background; radius: choice.colors.radius || 8
            Rectangle { width: 24; height: parent.height; color: choice.colors.sidebar || Theme.sidebar }
            Rectangle { x: 6; y: 12; width: 12; height: 3; radius: 1; color: choice.colors.accent || Theme.accent }
            Repeater {
                model: 3
                Rectangle {
                    required property int index
                    x: 32+index*((parent.width-40)/3); y: 12
                    width: (parent.width-48)/3; height: 48; radius: Math.min(5,choice.colors.radius || 8)
                    color: Qt.tint(choice.colors.surface || Theme.surface,Qt.rgba(previewAccent.r,previewAccent.g,previewAccent.b,.1+index*.15))
                    readonly property color previewAccent: choice.colors.accent || Theme.accent
                    Rectangle { x: 4; y: parent.height-8; width: parent.width-8; height: 3; radius: 1; color: choice.colors.accent || Theme.accent }
                }
            }
        }
        Label { x: 12; y: 89; text: choice.colors.name || ""; color: Theme.text; font.pixelSize: 13 }
        Label { anchors.right: parent.right; anchors.rightMargin: 12; y: 87; text: "✓"; color: Theme.accent; visible: choice.selected; font.pixelSize: 16 }
    }
}
