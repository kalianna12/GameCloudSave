import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: picker
    property string gameId: ""
    property string gameName: ""
    readonly property var record: backend.games.find(function(game) { return game.id===picker.gameId }) || ({})
    function reset() {
        query.text=gameName
        provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===backend.settings.cover_source }))
        imageUrl.text=""
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        RowLayout {
            Rectangle {
                Layout.preferredWidth: 62; Layout.preferredHeight: 92; color: Theme.sidebar; radius: 4
                Image { id: currentArt; anchors.fill: parent; source: picker.record.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize: Qt.size(186,276) }
                Label { visible: !picker.record.coverUrl || currentArt.status===Image.Error; text: "暂无封面"; anchors.centerIn: parent; color: Theme.secondary; font.pixelSize: 10 }
            }
            ColumnLayout {
                Layout.fillWidth: true; spacing: 6
                Label { text: "为这款游戏选择封面"; font.pixelSize: 18; font.bold: true }
                Label { text: "搜索后查看图片，点击“使用此封面”保存；也可选择本地图片。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: query; objectName: "gameCoverQuery"; text: picker.gameName; placeholderText: "游戏名称"; Layout.fillWidth: true; Layout.minimumWidth: 80 }
            AppComboBox { id: provider; objectName: "gameCoverProvider"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 180 }
            AppButton { text: (backend.coverProviders[provider.currentIndex] || {}).kind==="browser" ? "打开搜索" : "搜索封面"; highlighted: true; enabled: !backend.busy && !!query.text; onClicked: { if((backend.coverProviders[provider.currentIndex] || {}).kind==="browser") Qt.openUrlExternally(backend.coverBrowserUrl(query.text,provider.currentValue));else backend.searchGameCovers(picker.gameId,query.text,provider.currentValue,ai.checked) } }
        }
        CheckBox { id: ai; text: "用 DeepSeek 辅助识别游戏名称"; checked: backend.settings.ai_enabled && backend.settings.has_ai_key; enabled: backend.settings.has_ai_key && !backend.busy }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: imageUrl; Layout.fillWidth: true; placeholderText: "图片链接（可选）" }
            AppButton { text: "使用链接"; enabled: !backend.busy && !!imageUrl.text; onClicked: backend.useCoverUrl("game",picker.gameId,imageUrl.text) }
            AppButton { text: "选择本地图片"; enabled: !backend.busy; onClicked: backend.useLocalCover("game",picker.gameId) }
        }
        GridView {
            id: results; objectName: "gameCoverResults"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            model: backend.coverSearchTarget==="game:"+picker.gameId ? backend.coverResults : []
            cellWidth: width/Math.max(1,Math.floor(width/170)); cellHeight: 268
            delegate: Item {
                required property var modelData; width: results.cellWidth; height: results.cellHeight
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 6; spacing: 6
                    Image { source: modelData.image; asynchronous: true; fillMode: Image.PreserveAspectFit; Layout.fillWidth: true; Layout.preferredHeight: 190; sourceSize: Qt.size(300,450); onStatusChanged: if(status===Image.Error && modelData.fallback && source.toString()!==modelData.fallback) source=modelData.fallback }
                    Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                    AppButton { text: "使用此封面"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: backend.applyCover("game",picker.gameId,modelData.id) }
                }
            }
            ScrollBar.vertical: ScrollBar {}
            Label { visible: results.count===0; anchors.centerIn: parent; text: backend.busy ? "正在搜索，可切换页面或关闭窗口" : "输入名称并搜索，候选封面会显示在这里"; color: Theme.secondary; width: Math.max(0,parent.width-30); wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
        }
    }
}
