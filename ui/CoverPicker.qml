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
    readonly property var record: backend.games.find(function(game) { return game.id===picker.gameId }) || ({})
    function reset() {
        browserOpen=false;pictureTabs.currentIndex=0
        query.text=gameName
        provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===backend.settings.cover_source }))
        imageUrl.text=""
    }
    function search() {
        if((backend.coverProviders[provider.currentIndex] || {}).kind==="browser") {
            browserToken=backend.beginInlineImages("game",gameId,provider.currentValue,artKind)
            browserUrl=backend.artworkBrowserUrl(query.text,provider.currentValue,artKind);browserOpen=!!browserToken
        } else { browserOpen=false;backend.searchTargetArtwork("game",gameId,query.text,provider.currentValue,artKind,ai.checked) }
    }
    onVisibleChanged: if(!visible) browserOpen=false
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
        TabBar { id: pictureTabs; objectName: "artworkTabs"; Layout.fillWidth: true; onCurrentIndexChanged: picker.browserOpen=false; TabButton { text: "封面" } TabButton { text: "横幅" } }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: query; objectName: "gameCoverQuery"; text: picker.gameName; placeholderText: "游戏名称"; Layout.fillWidth: true; Layout.minimumWidth: 80; onAccepted: if(!backend.busy) picker.search() }
            AppComboBox { id: provider; objectName: "gameCoverProvider"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 180; onCurrentIndexChanged: picker.browserOpen=false }
            AppButton { objectName: "searchGameArtwork"; text: "搜索图片"; highlighted: true; enabled: !backend.busy && !!query.text; onClicked: picker.search() }
        }
        CheckBox { id: ai; visible: (backend.coverProviders[provider.currentIndex] || {}).kind!=="browser"; text: "用 DeepSeek 辅助识别游戏名称"; checked: backend.settings.ai_enabled && backend.settings.has_ai_key; enabled: backend.settings.has_ai_key && !backend.busy }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: imageUrl; Layout.fillWidth: true; placeholderText: "图片链接（可选）" }
            AppButton { text: "使用链接"; enabled: !backend.busy && !!imageUrl.text; onClicked: { if(picker.artKind==="background") backend.useBackgroundUrl(picker.gameId,imageUrl.text);else backend.useCoverUrl("game",picker.gameId,imageUrl.text) } }
            AppButton { text: "选择本地图片"; enabled: !backend.busy; onClicked: { if(picker.artKind==="background") backend.useLocalBackground(picker.gameId);else backend.useLocalCover("game",picker.gameId) } }
        }
        Loader {
            id: browser; Layout.fillWidth: true; Layout.fillHeight: true; visible: picker.browserOpen; active: picker.visible && picker.browserOpen
            source: active ? "InlineImageBrowser.qml" : ""
            onLoaded: { item.token=Qt.binding(function() { return picker.browserToken });item.providerId=Qt.binding(function() { return provider.currentValue });item.searchUrl=Qt.binding(function() { return picker.browserUrl }) }
            Connections { target: browser.item; function onCollected(count) { picker.browserOpen=false } function onDismissed() { picker.browserOpen=false } }
        }
        GridView {
            id: results; objectName: "gameCoverResults"; visible: !picker.browserOpen; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: backend.coverSearchTarget==="game:"+picker.gameId ? backend.coverResults : []
            cellWidth: width/Math.max(1,Math.floor(width/190)); cellHeight: 240
            delegate: ArtworkCandidate {
                required property var modelData; width: results.cellWidth; height: results.cellHeight; record: modelData; kind: picker.artKind
                onChosen: function(kind) { if(kind==="background") backend.applyBackground(picker.gameId,modelData.id);else backend.applyCover("game",picker.gameId,modelData.id) }
            }
            ScrollBar.vertical: ScrollBar {}
            Label { visible: results.count===0; anchors.centerIn: parent; text: backend.busy ? "正在搜索，可切换页面或关闭窗口" : "输入名称并搜索，候选封面会显示在这里"; color: Theme.secondary; width: Math.max(0,parent.width-30); wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
        }
    }
}
