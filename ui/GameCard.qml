import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: card
    property var game
    property bool scrolling: false
    property bool selected: false
    property string transferState: "idle"
    signal launchRequested()
    signal settingsRequested()
    signal cloudRequested()
    signal removeRequested()
    signal favoriteRequested()
    radius: Theme.radius
    color: hover.hovered && !scrolling ? Qt.lighter(Theme.surface,1.08) : Theme.surface
    border.color: selected ? Theme.accent : hover.hovered && !scrolling ? Theme.outline : "transparent"
    border.width: selected ? 3 : 1
    Behavior on border.color { ColorAnimation { duration: Theme.motion ? 120 : 0 } }
    Behavior on color { ColorAnimation { duration: Theme.motion && !card.scrolling ? 120 : 0 } }
    Rectangle {
        objectName: "cardFocusRing"
        anchors.fill: parent; z: 100; radius: card.radius
        color: "transparent"; border.color: Theme.accent
        border.width: card.selected ? 3 : 0
        visible: card.selected
    }
    HoverHandler { id: hover; enabled: !backend.controllerMode }
    Item {
        id: coverArea; width: parent.width; height: card.width * Theme.coverAspect
        Rectangle {
            id: poster; objectName: "coverSurface"
            anchors.fill: parent; color: Theme.sidebar; clip: true; radius: 10
            transform: [
                Rotation { objectName: "coverYaw"; origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 0; axis.y: 1; axis.z: 0; angle: coverEffect.yaw },
                Rotation { objectName: "coverPitch"; origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 1; axis.y: 0; axis.z: 0; angle: coverEffect.pitch }
            ]
            Image {
                id: art
                objectName: "coverImage"
                property int decodeWidth: card.width*Screen.devicePixelRatio<=360 ? 360 : card.width*Screen.devicePixelRatio<=720 ? 720 : 1080
                anchors.fill: parent; source: decodeWidth>360 && card.game.coverHighUrl ? card.game.coverHighUrl : card.game.coverUrl
                fillMode: Image.PreserveAspectCrop
                asynchronous: true; cache: true
                sourceSize: Qt.size(decodeWidth, 0)
            }
            Label { visible: !card.game.coverUrl || art.status===Image.Error; anchors.centerIn: parent; width: parent.width-26; text: card.game.name; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; color: Theme.secondary; font.pixelSize: 23; font.bold: true }
        }
        MouseArea { anchors.fill: parent; z: 1; enabled: !backend.busy; cursorShape: Qt.PointingHandCursor; onClicked: card.settingsRequested() }
        CoverEffects { id: coverEffect; anchors.fill: parent; z: 5; surface: poster; identity: card.game.id || ""; controllerFocused: card.selected && backend.controllerMode; suspended: card.scrolling }
        AchievementBadge { id: achievements;gameId: card.game.id || "";x: 7;y: 7 }
        NewGameBadge { visible: !!card.game.isNew;x: 7;y: achievements.visible ? achievements.y+achievements.height+5 : 7 }
        IconButton { z: 6; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; width: 32; height: 32; iconName: "star"; overArtwork: true; accent: !!card.game.favorite; visible: card.game.favorite || hover.hovered; hint: card.game.favorite ? "取消收藏" : "收藏"; enabled: !backend.busy; onClicked: card.favoriteRequested() }
    }
    Item {
        height: 82
        x: 10; y: coverArea.height+8; width: parent.width-20
        TitleLabel { objectName: "gameTitle"; scrolling: card.scrolling; text: card.game.name; width: parent.width; height: 32; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 13; font.weight: Font.DemiBold; }
        RowLayout {
            objectName: "gameActions"
            y: 38; width: card.width-20; height: 34; spacing: 0
            Repeater {
                model: ["play","settings","cloud","delete"]
                Item {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true; Layout.preferredWidth: index===0 ? 64 : 32; Layout.preferredHeight: 34
                    IconButton {
                        anchors.centerIn: parent
                        objectName: "action-"+modelData
                        width: parent.width-2; height: 32
                        iconName: modelData; accent: index===0
                        label: index===0 ? "启动" : ""
                        transferState: index===2 ? card.transferState : "idle"
                        hint: index===0 ? "启动" : index===1 ? "设置" : index===2 ? (card.transferState==="uploading" ? "正在上传" : card.transferState==="success" ? "上传成功" : card.transferState==="failed" ? "上传失败，可重试" : "云存档") : "移除"
                        enabled: !backend.busy
                        onClicked: { if(index===0) card.launchRequested(); else if(index===1) card.settingsRequested(); else if(index===2) card.cloudRequested(); else card.removeRequested() }
                    }
                }
            }
        }
    }
}
