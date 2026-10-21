import QtQuick
import QtQuick.Controls
Rectangle {
    objectName: "newGameBadge"
    width: 48;height: 21;radius: 4;z: 8;color: Theme.accent
    Label { anchors.centerIn: parent;text: "新加入";font.pixelSize: 10;color: Theme.onAccent;font.weight: Font.DemiBold }
}
