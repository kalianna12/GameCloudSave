import QtQuick
import QtQuick.Controls
Button {
    id: control
    implicitHeight: 36
    implicitWidth: Math.max(80, contentItem.implicitWidth + 28)
    leftPadding: 14; rightPadding: 14; topPadding: 8; bottomPadding: 8
    topInset: 0; bottomInset: 0
    hoverEnabled: true
    font.pixelSize: 13
    contentItem: Text {
        text: control.text; font: control.font
        color: !control.enabled ? Theme.secondary : control.highlighted ? Theme.onAccent : Theme.text
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    background: Rectangle {
        radius: 5
        color: control.highlighted && control.enabled ? Theme.accent : control.down || control.checked ? Theme.hover : control.hovered ? Theme.hover : Theme.surface
        border.width: control.activeFocus ? 2 : 1
        border.color: control.activeFocus ? Theme.text : control.highlighted && control.enabled ? Theme.accent : Theme.border
        opacity: control.enabled ? 1 : 0.6
    }
}
