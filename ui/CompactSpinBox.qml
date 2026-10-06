import QtQuick
import QtQuick.Controls
SpinBox {
    id: control
    implicitWidth: 112; implicitHeight: 42
    leftPadding: 32; rightPadding: 32; topPadding: 0; bottomPadding: 0
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
    contentItem: Text {
        text: control.textFromValue(control.value,control.locale)
        color: "#e2eee5"; font.pixelSize: 13
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
    }
    background: Rectangle { radius: 8; color: "#1d2b21"; border.color: control.activeFocus ? "#a2dd83" : "#3a4c3f" }
    up.indicator: Rectangle {
        x: control.width-width; width: 32; height: control.height; radius: 8
        color: control.up.hovered ? "#354b3b" : "transparent"
        Text { anchors.centerIn: parent; text: "+"; font.pixelSize: 23; color: control.value<control.to ? "#b6df9c" : "#667b6c" }
    }
    down.indicator: Rectangle {
        width: 32; height: control.height; radius: 8
        color: control.down.hovered ? "#354b3b" : "transparent"
        Text { anchors.centerIn: parent; text: "−"; font.pixelSize: 23; color: control.value>control.from ? "#b6df9c" : "#667b6c" }
    }
}
