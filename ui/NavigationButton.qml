import QtQuick
import QtQuick.Controls
import QtQuick.Window
AbstractButton {
    id: control
    property string iconName: "grid"
    property bool selected: false
    width: 152; height: 42
    hoverEnabled: true
    Accessible.name: text
    background: Rectangle {
        radius: 5
        color: control.selected ? Theme.hover : control.hovered ? Theme.hover : "transparent"
        border.color: control.activeFocus ? Theme.text : "transparent"
    }
    contentItem: Item {
        Image {
            x: 12; anchors.verticalCenter: parent.verticalCenter
            width: 20; height: 20; source: backend.iconSource(control.iconName,Theme.text.toString())
            sourceSize: Qt.size(Math.ceil(width*Screen.devicePixelRatio),Math.ceil(height*Screen.devicePixelRatio))
        }
        Text { x: 44; width: control.width-50; elide: Text.ElideRight; anchors.verticalCenter: parent.verticalCenter; text: control.text; color: Theme.text; font.pixelSize: 13 }
    }
}
