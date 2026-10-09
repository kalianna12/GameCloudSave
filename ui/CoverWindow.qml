import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: covers; width: 920; height: 720; minimumWidth: 800; minimumHeight: 600; title: "搜索封面"
    color: Theme.background; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent; font.family: "Microsoft YaHei UI"
    property string scope: "game"
    property string targetId: ""
    function openSearch(kind,ident,name,source) { if(backend.busy) return;backend.clearCoverSearch();scope=kind;targetId=ident;query.text=name;provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===(source || backend.settings.cover_source) }));show();raise();requestActivate() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "搜索封面"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: covers.close() } }
        RowLayout { AppTextField { id: query; Layout.fillWidth: true; placeholderText: "中文或英文游戏名称" }
            AppComboBox { id: provider; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 210; Layout.minimumWidth: 190 }
            AppButton { text: (backend.coverProviders[provider.currentIndex] || {}).kind==="browser" ? "浏览器搜索" : "搜索"; enabled: !backend.busy && !!query.text; highlighted: true; onClicked: { if((backend.coverProviders[provider.currentIndex] || {}).kind==="browser") Qt.openUrlExternally(backend.coverBrowserUrl(query.text,provider.currentValue));else backend.searchCovers(query.text,provider.currentValue,ai.checked) } }
        }
        CheckBox { id: ai; text: "DeepSeek 辅助识别英文名称"; enabled: backend.settings.has_ai_key; checked: backend.settings.ai_enabled }
        Label { visible: (backend.coverProviders[provider.currentIndex] || {}).kind==="browser"; text: "浏览器中选好图片后，可粘贴图片直链或导入已下载的图片。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        RowLayout { AppTextField { id: imageUrl; Layout.fillWidth: true; placeholderText: "图片直链 http / https" } AppButton { text: "使用链接图片"; enabled: !backend.busy && !!imageUrl.text; onClicked: backend.useCoverUrl(covers.scope,covers.targetId,imageUrl.text) } AppButton { text: "选择本地图片"; enabled: !backend.busy; onClicked: backend.useLocalCover(covers.scope,covers.targetId) } }
        GridView { id: grid; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: backend.coverResults; cellWidth: width/Math.max(1,Math.floor(width/190)); cellHeight: 300
            delegate: Item {
                required property var modelData; width: grid.cellWidth; height: grid.cellHeight
                ColumnLayout { anchors.fill: parent; anchors.margins: 8; spacing: 5
                    Image { Layout.fillWidth: true; Layout.preferredHeight: 215; source: modelData.image; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(300,450); onStatusChanged: if(status===Image.Error && modelData.fallback && source.toString()!==modelData.fallback) source=modelData.fallback }
                    Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                    AppButton { text: "使用此封面"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: backend.applyCover(covers.scope,covers.targetId,modelData.id) }
                }
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
    }
}
