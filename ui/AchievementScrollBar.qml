import QtQuick
import QtQuick.Controls

ScrollBar {
    id: bar
    width: 12;implicitWidth: 12;padding: 2
    interactive: true;hoverEnabled: true;policy: ScrollBar.AsNeeded
    minimumSize: Math.min(1,28/Math.max(1,height))
    z: 20
    contentItem: Rectangle {
        implicitWidth: 8;implicitHeight: 28;radius: 4
        color: bar.pressed ? Theme.accent : bar.hovered ? Theme.secondary : Theme.border
        opacity: bar.active || bar.hovered || bar.pressed ? 1 : .65
    }
}
