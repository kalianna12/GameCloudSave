import QtQuick
import QtQuick.Templates as T
T.TextField {
    id: control
    implicitWidth: 180; implicitHeight: 38
    leftPadding: 11; rightPadding: 11; topPadding: 8; bottomPadding: 8
    color: Theme.text; selectionColor: Theme.accent; selectedTextColor: Theme.onAccent
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    selectByMouse: true
    Text {
        x: control.leftPadding; y: control.topPadding
        width: control.availableWidth; height: control.availableHeight
        text: control.placeholderText; font: control.font; color: Theme.secondary
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        visible: !control.text.length && !control.preeditText.length
    }
    background: Rectangle {
        radius: 9; color: Theme.surface
        border.color: control.activeFocus ? Theme.accent : Theme.outline
        border.width: control.activeFocus ? 2 : 1
    }
}
