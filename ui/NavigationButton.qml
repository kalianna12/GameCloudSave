import QtQuick
import QtQuick.Controls
import QtQuick.Window
AbstractButton {
    id: control
    property string iconName: "grid"
    property bool selected: false
    width: 152; height: 44
    hoverEnabled: !backend.controllerMode
    Accessible.name: text
    background: Rectangle {
        radius: 10
        color: control.selected ? Theme.selection : control.hovered ? Theme.hover : "transparent"
        border.color: control.activeFocus ? Theme.accent : "transparent"
        Rectangle { x: 0; anchors.verticalCenter: parent.verticalCenter; width: 3; height: 18; radius: 1.5; color: Theme.accent; visible: control.selected }
    }
    contentItem: Item {
        Image {
            x: 12; anchors.verticalCenter: parent.verticalCenter
            width: 19; height: 19; source: backend.iconSource(control.iconName,(control.selected ? Theme.accent : Theme.secondary).toString())
            sourceSize: Qt.size(Math.ceil(width*Screen.devicePixelRatio),Math.ceil(height*Screen.devicePixelRatio))
        }
        Text { x: 44; width: control.width-50; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter; text: control.text; color: control.selected || control.hovered ? Theme.text : Theme.secondary; font.pixelSize: 13; font.weight: control.selected ? Font.DemiBold : Font.Normal }
    }
}
