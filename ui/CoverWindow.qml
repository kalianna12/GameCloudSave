import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    ControlFocus {}
    id: covers; width: 920; height: 720; minimumWidth: 800; minimumHeight: 600; title: "搜索封面"
    color: Theme.background; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent; font.family: "Microsoft YaHei UI"
    property string scope: "game"
    property string targetId: ""
    property bool browserOpen: false
    property string browserToken: ""
    property url browserUrl
    function resetSearch() { if(backend.coverSearchTarget===covers.scope+":"+covers.targetId) backend.clearCoverSearch() }
    function search() { browserOpen=false;backend.searchTargetArtwork(scope,targetId,query.text,provider.currentValue,"cover",ai.checked) }
    onVisibleChanged: if(!visible) { browserOpen=false;backend.cancelArtworkSearch(scope,targetId) }
    function openSearch(kind,ident,name,source) { if(backend.busy) return;backend.clearCoverSearch();scope=kind;targetId=ident;query.text=name;provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===(source || backend.settings.cover_source) }));show();raise();requestActivate() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "搜索封面"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: covers.close() } }
        RowLayout { AppTextField { id: query; Layout.fillWidth: true; placeholderText: "中文或英文游戏名称" }
            AppComboBox { id: provider; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 210; Layout.minimumWidth: 190; onCurrentIndexChanged: covers.resetSearch() }
            AppButton { text: "搜索图片"; enabled: !backend.busy && !!query.text; highlighted: true; onClicked: covers.search() }
        }
        CheckBox { id: ai; text: "DeepSeek 辅助识别英文名称"; enabled: backend.settings.has_ai_key; checked: backend.settings.ai_enabled }
        RowLayout { AppTextField { id: imageUrl; Layout.fillWidth: true; placeholderText: "图片直链 http / https" } AppButton { text: "使用链接图片"; enabled: !backend.busy && !!imageUrl.text; onClicked: backend.useCoverUrl(covers.scope,covers.targetId,imageUrl.text) } AppButton { text: "选择本地图片"; enabled: !backend.busy; onClicked: backend.useLocalCover(covers.scope,covers.targetId) } }
        ArtworkResults { visible: !covers.browserOpen; Layout.fillWidth: true; Layout.fillHeight: true; targetKey: covers.scope+":"+covers.targetId
            onChosen: function(ident,kind) { backend.applyCover(covers.scope,covers.targetId,ident) }
        }
        Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
    }
}
