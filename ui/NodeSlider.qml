import QtQuick
import QtQuick.Controls
Slider {
    id: control
    from: 196; to: 360; stepSize: 1
    implicitWidth: 175; implicitHeight: 45
    topPadding: 0; bottomPadding: 18
    background: Item {
        x: control.leftPadding; y: control.topPadding + control.availableHeight / 2 - 3
        width: control.availableWidth; height: 6
        Rectangle { anchors.fill: parent; radius: 3; color: "#45494e" }
        Rectangle { width: control.visualPosition * parent.width; height: parent.height; radius: 3; color: "#80c942" }
        Repeater {
            model: [196, 240, 280, 320, 360]
            Item {
                required property int modelData
                x: (modelData-control.from)/(control.to-control.from)*parent.width
                Rectangle { x: -2; y: 1; width: 4; height: 4; radius: 2; color: "#c6c9ce" }
                Text { x: -12; y: 12; text: modelData; font.pixelSize: 9; color: "#a6a9ae" }
            }
        }
    }
    handle: Rectangle {
        x: control.leftPadding + control.visualPosition * (control.availableWidth-width)
        y: control.topPadding + control.availableHeight / 2 - height / 2
        width: 15; height: 15; radius: 8; color: "#80c942"
        border.width: control.pressed ? 2 : 0; border.color: "#f0f1f2"
    }
}
