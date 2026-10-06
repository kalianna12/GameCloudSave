import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Rectangle {
    id: card
    property var game
    property bool scrolling: false
    property string transferState: "idle"
    signal launchRequested()
    signal settingsRequested()
    signal cloudRequested()
    signal removeRequested()
    radius: 12
    color: hover.hovered && !scrolling ? "#25342a" : "#1c2720"
    border.color: hover.hovered && !scrolling ? "#56774f" : "#2b3930"
    HoverHandler { id: hover }
    Rectangle {
        id: poster
        width: parent.width; height: card.width * 1.38; color: "#27382c"; clip: true
        Image {
            id: art
            objectName: "coverImage"
            anchors.fill: parent; source: card.game.coverUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true; cache: true
            sourceSize: Qt.size(360, 0)
        }
        Label { visible: !card.game.coverUrl; anchors.centerIn: parent; width: parent.width-26; text: card.game.name; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; color: "#9ed282"; font.pixelSize: 23; font.bold: true }
        Rectangle {
            x: 10; y: 10; width: badge.implicitWidth+18; height: 23; radius: 5; color: "#de17251a"
            Label { id: badge; anchors.centerIn: parent; text: card.game.installed ? "已安装" : "未安装"; font.pixelSize: 10; color: card.game.installed ? "#b5f68b" : "#b6c1b8" }
        }
    }
    ColumnLayout {
        x: 10; y: poster.height+10; width: parent.width-20
        spacing: 6
        Label { text: card.game.name; Layout.fillWidth: true; elide: Text.ElideRight; color: "#f0f5f1"; font.pixelSize: 14; font.bold: true; ToolTip.visible: hover.hovered && !card.scrolling; ToolTip.delay: 1000; ToolTip.text: text }
        Label { text: card.game.saveSet ? "本机存档已配置" : "选择本机存档目录后可备份"; font.pixelSize: 10; color: card.game.saveSet ? "#a2c592" : "#8b9e90"; Layout.fillWidth: true; elide: Text.ElideRight }
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
                        hint: index===0 ? "启动游戏" : index===1 ? "游戏本机设置" : index===2 ? (card.transferState==="uploading" ? "正在上传" : card.transferState==="success" ? "上传成功 / 快照历史" : card.transferState==="failed" ? "上传失败 / 可补传" : "云存档与快照历史") : "移除管理条目"
                        enabled: !backend.busy
                        onClicked: { if(index===0) card.launchRequested(); else if(index===1) card.settingsRequested(); else if(index===2) card.cloudRequested(); else card.removeRequested() }
                    }
                }
            }
        }
    }
}
