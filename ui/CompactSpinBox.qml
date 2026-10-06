import QtQuick
import QtQuick.Controls
SpinBox {
    id: control
    implicitWidth: 112; implicitHeight: 42
    leftPadding: 32; rightPadding: 32; topPadding: 0; bottomPadding: 0
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
    contentItem: Text {
        text: control.textFromValue(control.value,control.locale)
        color: "#a6a9ae"; font.pixelSize: 13
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle { radius: 5; color: Theme.surface; border.color: control.activeFocus ? Theme.text : Theme.border }
    up.indicator: Rectangle {
        x: control.width-width; width: 32; height: control.height; radius: 8
        color: control.up.hovered ? Theme.hover : "transparent"
        Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 23; color: control.value<control.to ? "#a6a9ae" : "#a6a9ae" }
    }
    down.indicator: Rectangle {
        width: 32; height: control.height; radius: 8
        color: control.down.hovered ? Theme.hover : "transparent"
        Text { anchors.centerIn: parent; text: "−"; font.pixelSize: 23; color: control.value>control.from ? "#a6a9ae" : "#a6a9ae" }
    }
}
