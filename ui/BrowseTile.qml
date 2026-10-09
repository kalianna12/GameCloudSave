import QtQuick
import QtQuick.Controls
AbstractButton {
    id: tile
    readonly property bool libraryTile: true
    property var record: ({})
    property bool selected: false
    signal focusRequested()
    onActiveFocusChanged: if(activeFocus) focusRequested()
    hoverEnabled: !backend.controllerMode; padding: 0
    implicitWidth: 236; implicitHeight: 148
    Accessible.name: (record.name || "")+" "+record.count+" 款游戏"
    background: Rectangle { radius: 6; color: Theme.surface; border.color: tile.hovered ? Theme.accent : Theme.border }
    contentItem: Item {
        clip: true
        Row {
            anchors.fill: parent
            Repeater { model: tile.record.games || []
                Image { required property var modelData; width: tile.width/Math.max(1,(tile.record.games || []).length); height: tile.height; source: modelData.coverUrl || ""; asynchronous: true; cache: true; sourceSize: Qt.size(240,360); fillMode: Image.PreserveAspectCrop }
            }
        }
        Rectangle { anchors.fill: parent; color: "#50000000" }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 52; color: "#e0181a1c"
            Column {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                spacing: 3
                Label { width: parent.width; text: tile.record.name || ""; font.bold: true; font.pixelSize: 16; color: "#ffffff"; elide: Text.ElideRight }
                Label { text: tile.record.count+" 款游戏"; font.pixelSize: 11; color: "#d1d6db" }
            }
        }
        Rectangle { objectName: "tileFocusRing"; readonly property real focusWidth: border.width; anchors.fill: parent; color: "transparent"; radius: 6; border.width: tile.selected ? 3 : tile.hovered ? 2 : 0; border.color: tile.selected ? Theme.accent : Theme.secondary; Behavior on border.width { NumberAnimation { duration: Theme.motion ? 100 : 0 } } }
    }
}
