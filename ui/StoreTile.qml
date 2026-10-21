import QtQuick
import QtQuick.Controls
AbstractButton {
    id: tile
    readonly property bool libraryTile: true
    property var record: ({})
    property bool selected: false
    property bool scrolling: false
    signal focusRequested()
    onActiveFocusChanged: if(activeFocus) focusRequested()
    hoverEnabled: !backend.controllerMode
    padding: 0
    Accessible.name: (record.name || "")+"，"+(record.platformLabel || "")+"，"+(record.price || "查看商店")
    background: Item {}
    contentItem: Item {
        Item {
            id: coverArea
            width: parent.width; height: parent.height-55
            Rectangle {
                id: poster; anchors.fill: parent; color: Theme.surface; radius: 8; clip: true
                transform: [
                    Rotation { origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 0; axis.y: 1; axis.z: 0; angle: effect.yaw },
                    Rotation { origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 1; axis.y: 0; axis.z: 0; angle: effect.pitch }
                ]
                Image { id: artwork; objectName: "storeArtwork"; anchors.fill: parent; source: tile.record.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize: Qt.size(640,400) }
                Label { anchors.centerIn: parent; width: parent.width-24; text: tile.record.name || ""; visible: !artwork.source.toString() || artwork.status===Image.Error; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: Theme.secondary }
                Rectangle {
                    anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                    height: 44
                    gradient: Gradient { GradientStop { position: 0; color: "#00000000" } GradientStop { position: 1; color: "#dd000000" } }
                    Label {
                        anchors { left: parent.left; bottom: parent.bottom; margins: 8 }
                        text: tile.record.platformLabel || ""; color: "white"; font.pixelSize: 11
                    }
                }
            }
            CoverEffects { id: effect; anchors.fill: parent; surface: poster; identity: tile.record.id || ""; controllerFocused: tile.selected && backend.controllerMode; suspended: tile.scrolling }
            Rectangle { anchors.fill: parent; z: 10; radius: 8; color: "transparent"; border.width: tile.selected ? 3 : tile.hovered ? 2 : 0; border.color: tile.selected ? Theme.accent : Theme.secondary }
            Rectangle {
                visible: tile.record.discount>0; anchors { left: parent.left; top: parent.top; margins: 8 }
                width: discountLabel.implicitWidth+14; height: 25; radius: 4; color: Theme.accent
                Label { id: discountLabel; anchors.centerIn: parent; text: "−"+(tile.record.discount || 0)+"%"; color: Theme.onAccent; font.bold: true; font.pixelSize: 12 }
            }
            IconButton {
                objectName: "retryStoreArtwork"; z: 12
                anchors { right: parent.right; top: parent.top; margins: 8 }
                iconName: "refresh"; hint: tile.record.artworkLoading ? "正在重试图片" : "图片加载失败，点击重试"
                overArtwork: true
                visible: artwork.status===Image.Error || (!!tile.record.artworkFailed && artwork.status!==Image.Ready)
                enabled: !tile.record.artworkLoading
                onClicked: backend.recommendations.retryArtwork(tile.record.id,tile.record.category)
            }
        }
        TitleLabel { y: coverArea.height+8; width: parent.width; text: tile.record.name || ""; scrolling: tile.scrolling; elide: Text.ElideRight; font.pixelSize: 13; font.weight: Font.DemiBold; color: Theme.text }
        Row {
            y: coverArea.height+31; spacing: 8
            Label { text: tile.record.price || "查看商店"; color: tile.record.discount>0 ? Theme.accent : Theme.secondary; font.pixelSize: 12 }
            Label { text: tile.record.originalPrice || ""; font.strikeout: true; color: Theme.secondary; font.pixelSize: 11 }
        }
    }
}
