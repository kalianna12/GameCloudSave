import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: card
    property var record: ({})
    property string kind: "cover"
    property bool completion: false
    readonly property string imageUrl: kind==="background" ? record.background_url || "" : record.thumbnail || record.image || ""
    signal chosen(string kind)
    implicitHeight: completion ? 300 : 240
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 6; spacing: 4
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: card.completion ? 136 : 118; color: Theme.sidebar; radius: 5; clip: true
            Image { id: preview; anchors.fill: parent; anchors.margins: 3; source: card.imageUrl; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 440
                onStatusChanged: if(status===Image.Error && card.kind==="cover" && card.record.fallback && source.toString()!==card.record.fallback) source=card.record.fallback
            }
            Label { anchors.centerIn: parent; color: Theme.secondary; text: preview.status===Image.Error ? "预览加载失败" : card.kind==="background" ? (card.record.background_state==="unknown" ? "横幅查询失败" : "未找到横幅") : "暂无封面"; visible: !card.imageUrl || preview.status===Image.Error; font.pixelSize: 12 }
        }
        Label { text: card.record.name || ""; Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 12 }
        RowLayout {
            Layout.fillWidth: true
            Label { objectName: "candidateBannerStatus"; text: card.record.background_state==="unknown" ? "横幅查询失败" : card.record.background_url ? "有横幅" : card.record.background_state==="none" ? "无横幅" : "横幅未查询"; color: card.record.background_url ? Theme.accent : Theme.secondary; font.pixelSize: 11 }
            Item { Layout.fillWidth: true }
            Label { text: card.record.width && card.record.height ? card.record.width+" × "+card.record.height : card.record.provider || ""; color: Theme.secondary; font.pixelSize: 10 }
        }
        AppButton { objectName: "chooseArtwork"; text: card.completion ? (card.kind==="cover" ? "选为封面" : "选为横幅") : (card.kind==="cover" ? "使用此封面" : "使用此横幅"); Layout.fillWidth: true; enabled: !backend.busy && !!card.imageUrl; onClicked: card.chosen(card.kind) }
        AppButton { visible: card.completion && !!card.record.appid || card.completion && card.record.provider==="vndb"; text: "匹配这款游戏的资料"; flat: true; Layout.fillWidth: true; enabled: !backend.busy; onClicked: card.chosen("metadata") }
    }
}
