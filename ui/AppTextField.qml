import QtQuick
import QtQuick.Templates as T
T.TextField {
    id: control
    implicitWidth: 180; implicitHeight: 38
    leftPadding: 11; rightPadding: 11; topPadding: 8; bottomPadding: 8
    color: Theme.text; selectionColor: "#52743a"; selectedTextColor: "#ffffff"
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    selectByMouse: true
    Text {
        x: control.leftPadding; y: control.topPadding
        width: control.availableWidth; height: control.availableHeight
        text: control.placeholderText; font: control.font; color: "#989da4"
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        visible: !control.text.length && !control.preeditText.length
    }
    background: Rectangle {
        radius: 5; color: "#202225"
        border.color: control.activeFocus ? Theme.text : Theme.border
        border.width: control.activeFocus ? 2 : 1
    }
}
