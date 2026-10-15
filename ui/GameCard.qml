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
    radius: 6
    color: hover.hovered && !scrolling ? Theme.hover : Theme.surface
    border.color: selected ? Theme.accent : hover.hovered && !scrolling ? Theme.secondary : Theme.border
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
    Rectangle {
        id: poster
        width: parent.width; height: card.width * 1.38; color: Theme.sidebar; clip: true
        transform: [
            Rotation { origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 0; axis.y: 1; axis.z: 0; angle: coverEffect.yaw
                Behavior on angle { enabled: coverEffect.available; SpringAnimation { spring: 3; damping: .34; epsilon: .02 } } },
            Rotation { origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 1; axis.y: 0; axis.z: 0; angle: coverEffect.pitch
                Behavior on angle { enabled: coverEffect.available; SpringAnimation { spring: 3; damping: .34; epsilon: .02 } } }
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
        MouseArea { anchors.fill: parent; z: 1; enabled: !backend.busy; cursorShape: Qt.PointingHandCursor; onClicked: card.settingsRequested() }
        CoverEffects { id: coverEffect; anchors.fill: parent; z: 5; controllerFocused: card.selected && backend.controllerMode; suspended: card.scrolling }
        IconButton { z: 6; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; width: 32; height: 32; iconName: "star"; accent: !!card.game.favorite; visible: card.game.favorite || hover.hovered; hint: card.game.favorite ? "取消收藏" : "收藏"; enabled: !backend.busy; onClicked: card.favoriteRequested() }
    }
    ColumnLayout {
        x: 10; y: poster.height+10; width: parent.width-20
        spacing: 6
        Label { text: card.game.name; Layout.fillWidth: true; Layout.preferredHeight: 34; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 13; font.bold: true; ToolTip.visible: hover.hovered && !card.scrolling; ToolTip.delay: 1000; ToolTip.text: text+"\n发行日期: "+(card.game.release_date || "未知") }
        RowLayout {
            Layout.fillWidth: true; spacing: 5
            Image { source: backend.iconSource(card.game.platform==="other" ? "local" : card.game.platform || "local",Theme.secondary.toString()); Layout.preferredWidth: 15; Layout.preferredHeight: 15; sourceSize: Qt.size(45,45) }
            Label { text: (card.game.platform==="steam" ? "Steam" : card.game.platform==="epic" ? "Epic" : card.game.platform==="ubisoft" ? "Ubisoft" : "本地")+" / "+(card.game.installed ? "已安装" : "未安装") + (card.game.saveSet ? " / 可备份" : ""); font.pixelSize: 10; color: Theme.secondary; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        Label { objectName: "gameReleaseDate"; text: "发行："+(card.game.release_date || "未知"); Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11; color: Theme.secondary }
        RowLayout {
            objectName: "gameActions"
            Layout.fillWidth: true; spacing: 0
            Repeater {
                model: ["play","settings","cloud","delete"]
                Item {
                    required property string modelData
                    required property int index
                    Layout.fillWidth: true; Layout.preferredHeight: 42
                    IconButton {
                        anchors.centerIn: parent
                        objectName: "action-"+modelData
                        width: Math.min(42,parent.width-2); height: 38
                        iconName: modelData; accent: index===0
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
