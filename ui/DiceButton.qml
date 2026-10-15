import QtQuick
import QtQuick.Controls
AbstractButton {
    id: dice
    property bool selected: false
    property real turn: 0
    implicitWidth: 110; implicitHeight: 38
    hoverEnabled: !backend.controllerMode
    Accessible.name: "随机选择一款游戏"
    function animateRoll() { if(Theme.motion) roll.restart() }
    onClicked: animateRoll()
    background: Rectangle { color: dice.hovered ? Theme.hover : "transparent"; radius: Theme.controlRadius; border.color: dice.activeFocus ? Theme.accent : Theme.outline; border.width: dice.activeFocus ? 2 : 1 }
    contentItem: Item {
        Rectangle {
            x: 12; y: (parent.height-height)/2; width: 23; height: 23; radius: 5; rotation: dice.turn
            color: Theme.accent
            Repeater {
                model: [Qt.point(6,6),Qt.point(17,6),Qt.point(11.5,11.5),Qt.point(6,17),Qt.point(17,17)]
                Rectangle { required property var modelData; x: modelData.x-1.7; y: modelData.y-1.7; width: 3.4; height: 3.4; radius: 2; color: Theme.onAccent }
            }
        }
        Label { x: 44; anchors.verticalCenter: parent.verticalCenter; text: "随机游戏"; color: Theme.text; font.pixelSize: 13 }
    }
    SequentialAnimation { id: roll; NumberAnimation { target: dice; property: "turn"; from: 0; to: 180; duration: 320; easing.type: Easing.OutBack } PropertyAction { target: dice; property: "turn"; value: 0 } }
}
