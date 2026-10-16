import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: pane
    objectName: "manualEnrichmentPane"
    property var record: ({})
    readonly property var game: backend.games.find(function(g) { return g.id===pane.record.id }) || ({})
    readonly property bool browser: (backend.coverProviders[provider.currentIndex] || {}).kind==="browser"
    function canFill(key) { return !!(record.missing || {})[key] }
    signal backRequested()
    function reset(row) {
        record=row;query.text=row.matched_name || row.name;provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(p) { return p.id===backend.settings.cover_source }))
        var fields=row.fields || {}
        date.text=fields.release_date || game.release_date || "";tagText.text=(fields.tags || game.tags || []).join(", ");series.text=fields.series || game.series || ""
        category.currentIndex=Math.max(0,category.model.indexOf(fields.category || game.category || "其他"))
        cover.text="";background.text=""
    }
    function search() {
        if(browser) Qt.openUrlExternally(backend.enrichmentBrowserUrl(query.text,provider.currentValue))
        else backend.searchTargetCovers("enrichment",record.id,query.text,provider.currentValue,false)
    }
    function stage() {
        backend.previewEnrichmentValues(record.id,{release_date:date.text.trim(),category:category.currentText,tags:tagText.text.split(/[,，]/).map(function(t) { return t.trim() }).filter(Boolean),series:series.text.trim(),cover:cover.text.trim(),background:background.text.trim()})
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 10
        RowLayout {
            Layout.fillWidth: true
            AppButton { objectName: "manualBack"; text: "返回补全预览"; enabled: !backend.busy; onClicked: pane.backRequested() }
            Label { text: pane.record.name || ""; Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 20; font.weight: Font.DemiBold }
        }
        RowLayout {
            Layout.fillWidth: true
            AppTextField { id: query; objectName: "manualQuery"; Layout.fillWidth: true; placeholderText: "游戏原名或别名"; onAccepted: if(!backend.busy) pane.search() }
            AppComboBox { id: provider; objectName: "manualProvider"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 170 }
            AppButton { objectName: "manualSearch"; text: pane.browser ? "打开搜索" : "搜索资料"; highlighted: true; enabled: !backend.busy && !!query.text.trim(); onClicked: pane.search() }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
            ScrollView {
                Layout.preferredWidth: Math.min(350,pane.width*.42); Layout.fillHeight: true; clip: true
                ColumnLayout {
                    width: parent.width-16; spacing: 8
                    Label { text: "补充缺失资料"; font.pixelSize: 17; font.weight: Font.DemiBold }
                    Label { text: "发行日期"; color: Theme.secondary }
                    AppTextField { id: date; objectName: "manualDate"; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD"; enabled: pane.canFill("release_date") }
                    Label { text: "主分类"; color: Theme.secondary }
                    AppComboBox { id: category; Layout.fillWidth: true; model: backend.primaryCategories; enabled: pane.canFill("category") }
                    Label { text: "标签"; color: Theme.secondary }
                    AppTextField { id: tagText; objectName: "manualTags"; Layout.fillWidth: true; placeholderText: "逗号分隔，最多 6 个"; enabled: pane.canFill("tags") }
                    Label { text: "系列"; color: Theme.secondary }
                    AppTextField { id: series; objectName: "manualSeries"; Layout.fillWidth: true; enabled: pane.canFill("series") }
                    Label { text: "封面"; color: Theme.secondary }
                    RowLayout {
                        Layout.fillWidth: true
                        AppTextField { id: cover; objectName: "manualCover"; Layout.fillWidth: true; placeholderText: pane.canFill("cover") ? "图片链接或本地路径" : "保留已有封面"; enabled: pane.canFill("cover") }
                        AppButton { text: "本地"; enabled: !backend.busy && pane.canFill("cover"); onClicked: { var path=backend.pickFile("cover");if(path) cover.text=path } }
                    }
                    Label { text: "横幅背景"; color: Theme.secondary }
                    RowLayout {
                        Layout.fillWidth: true
                        AppTextField { id: background; objectName: "manualBackground"; Layout.fillWidth: true; placeholderText: pane.canFill("background") ? "横向图片链接或本地路径" : "保留已有横幅"; enabled: pane.canFill("background") }
                        AppButton { text: "本地"; enabled: !backend.busy && pane.canFill("background"); onClicked: { var path=backend.pickFile("cover");if(path) background.text=path } }
                    }
                    AppButton { objectName: "manualStage"; text: "加入补全预览"; highlighted: true; enabled: !backend.busy; onClicked: pane.stage() }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                Label { text: pane.browser ? "在浏览器检索，找到后填入左侧。" : "核对名称后选择结果，已有资料会保留。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                GridView {
                    id: candidates; objectName: "manualCandidates"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    model: backend.coverSearchTarget==="enrichment:"+pane.record.id ? backend.coverResults : []
                    cellWidth: width/Math.max(1,Math.floor(width/170)); cellHeight: 252
                    delegate: Item {
                        required property var modelData; width: candidates.cellWidth; height: candidates.cellHeight
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 6; spacing: 6
                            Image { Layout.fillWidth: true; Layout.preferredHeight: 160; source: modelData.image || ""; fillMode: Image.PreserveAspectFit; asynchronous: true; sourceSize.width: 240 }
                            Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight }
                            Label { text: modelData.released || modelData.provider || ""; color: Theme.secondary; font.pixelSize: 11 }
                            AppButton { text: "选择此结果"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: backend.previewEnrichmentCandidate(pane.record.id,modelData.id) }
                        }
                    }
                    ScrollBar.vertical: ScrollBar {}
                    Label { visible: candidates.count===0; anchors.centerIn: parent; width: parent.width-20; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: Theme.secondary; text: backend.busy ? "正在搜索…" : "可修改名称重试，或切换搜索来源。" }
                }
            }
        }
    }
}
