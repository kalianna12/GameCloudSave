import QtQuick
import QtQuick.Window
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
    radius: 6
    color: hover.hovered && !scrolling ? "#34373b" : "#27292c"
    border.color: hover.hovered && !scrolling ? "#62676e" : "#27292c"
    HoverHandler { id: hover }
    Rectangle {
        id: poster
        width: parent.width; height: card.width * 1.38; color: "#242629"; clip: true
        Image {
            id: art
            objectName: "coverImage"
            property int decodeWidth: card.width*Screen.devicePixelRatio<=360 ? 360 : card.width*Screen.devicePixelRatio<=720 ? 720 : 1080
            anchors.fill: parent; source: decodeWidth>360 && card.game.coverHighUrl ? card.game.coverHighUrl : card.game.coverUrl
            fillMode: Image.PreserveAspectCrop
            asynchronous: true; cache: true
            sourceSize: Qt.size(decodeWidth, 0)
        }
        Label { visible: !card.game.coverUrl; anchors.centerIn: parent; width: parent.width-26; text: card.game.name; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; color: "#a6a9ae"; font.pixelSize: 23; font.bold: true }
    }
    ColumnLayout {
        x: 10; y: poster.height+10; width: parent.width-20
        spacing: 6
        Label { text: card.game.name; Layout.fillWidth: true; Layout.preferredHeight: 34; maximumLineCount: 2; wrapMode: Text.Wrap; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 13; font.bold: true; ToolTip.visible: hover.hovered && !card.scrolling; ToolTip.delay: 1000; ToolTip.text: text }
        Label { text: (card.game.installed ? "已安装" : "未安装") + (card.game.saveSet ? "  /  可备份" : ""); font.pixelSize: 11; color: Theme.secondary; Layout.fillWidth: true; elide: Text.ElideRight }
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
