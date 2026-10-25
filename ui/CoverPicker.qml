import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: picker
    property string gameId: ""
    property string gameName: ""
    readonly property string artKind: pictureTabs.currentIndex===1 ? "background" : "cover"
    property bool browserOpen: false
    property string browserToken: ""
    property url browserUrl
    readonly property var record: { var revision=backend.libraryRevision;return backend.libraryGame(picker.gameId) }
    function reset() {
        browserOpen=false;pictureTabs.currentIndex=0
        query.text=gameName
        provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===backend.settings.cover_source }))
        imageUrl.text=""
    }
    function resetSearch() { if(backend.coverSearchTarget==="game:"+picker.gameId) backend.clearCoverSearch() }
    function search() { browserOpen=false;backend.searchTargetArtwork("game",gameId,query.text,provider.currentValue,artKind,ai.checked) }
    onVisibleChanged: if(!visible) { browserOpen=false;backend.cancelArtworkSearch("game",gameId) }
    ColumnLayout {
        anchors.fill: parent; spacing: 8
        RowLayout {
            Rectangle {
                Layout.preferredWidth: picker.artKind==="background" ? 112 : 44; Layout.preferredHeight: 64; color: Theme.sidebar; radius: 4
                Image { id: currentArt; anchors.fill: parent; source: picker.artKind==="background" ? picker.record.backgroundUrl || "" : picker.record.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(378,276) }
                Label { visible: !currentArt.source.toString() || currentArt.status===Image.Error; text: "尚未设置"; anchors.centerIn: parent; color: Theme.secondary; font.pixelSize: 10 }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 6
                Label { text: picker.artKind==="background" ? "影院横幅" : "游戏封面"; font.pixelSize: 18; font.bold: true }
                Label { text: picker.artKind==="background" ? "用于影院的大背景" : "用于游戏卡片与胶片列表"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            }
        }
        TabBar { id: pictureTabs; objectName: "artworkTabs"; Layout.fillWidth: true; onCurrentIndexChanged: picker.resetSearch(); TabButton { text: "封面" } TabButton { text: "横幅" } }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: query; objectName: "gameCoverQuery"; text: picker.gameName; placeholderText: "游戏名称"; Layout.fillWidth: true; Layout.minimumWidth: 80; onAccepted: if(!backend.busy) picker.search() }
            AppComboBox { id: provider; objectName: "gameCoverProvider"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 180; onCurrentIndexChanged: picker.resetSearch() }
            AppButton { objectName: "searchGameArtwork"; text: "搜索图片"; highlighted: true; enabled: !backend.busy && !!query.text; onClicked: picker.search() }
        }
        CheckBox { id: ai; visible: (backend.coverProviders[provider.currentIndex] || {}).kind==="api"; text: "用 DeepSeek 辅助识别游戏名称"; checked: backend.settings.ai_enabled && backend.settings.has_ai_key; enabled: backend.settings.has_ai_key && !backend.busy }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: imageUrl; Layout.fillWidth: true; placeholderText: "图片链接（可选）" }
            AppButton { text: "使用链接"; enabled: !backend.busy && !!imageUrl.text; onClicked: { if(picker.artKind==="background") backend.useBackgroundUrl(picker.gameId,imageUrl.text);else backend.useCoverUrl("game",picker.gameId,imageUrl.text) } }
            AppButton { text: "选择本地图片"; enabled: !backend.busy; onClicked: { if(picker.artKind==="background") backend.useLocalBackground(picker.gameId);else backend.useLocalCover("game",picker.gameId) } }
        }
        ProgressBar { visible: backend.artworkSearching && backend.coverSearchTarget==="game:"+picker.gameId; indeterminate: true; Layout.fillWidth: true; Layout.preferredHeight: 3 }
        ArtworkResults {
            id: results; objectName: "gameCoverResults"; visible: !picker.browserOpen; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            targetKey: "game:"+picker.gameId; kind: picker.artKind
            onChosen: function(ident,kind) { if(kind==="background") backend.applyBackground(picker.gameId,ident);else backend.applyCover("game",picker.gameId,ident) }
        }
    }
}
