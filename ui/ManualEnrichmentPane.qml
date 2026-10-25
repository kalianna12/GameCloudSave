import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: pane
    objectName: "manualEnrichmentPane"
    property var record: ({})
    readonly property var game: { var revision=backend.libraryRevision;return backend.libraryGame(pane.record.id || "") }
    readonly property bool browser: (backend.coverProviders[provider.currentIndex] || {}).kind==="browser"
    readonly property string artKind: imageKind.currentIndex===1 ? "background" : "cover"
    property bool browserOpen: false
    property string browserToken: ""
    property url browserUrl
    property var dirtyFields: ({})
    function mark(key) { var next=Object.assign({},dirtyFields);next[key]=true;dirtyFields=next }
    function canFill(key) { return !!(record.missing || {})[key] }
    signal backRequested()
    function reset(row) {
        browserOpen=false;imageKind.currentIndex=0;dirtyFields=({})
        record=row;query.text=row.matched_name || row.name;provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(p) { return p.id===backend.settings.cover_source }))
        var fields=row.fields || {}
        date.text=fields.release_date || game.release_date || "";tagText.text=(fields.tags || game.tags || []).join(", ");series.text=fields.series || game.series || ""
        category.currentIndex=Math.max(0,category.model.indexOf(fields.category || game.category || "其他"))
        cover.text="";background.text=""
    }
    function refreshProposal(row) {
        record=row;var fields=row.fields || {}
        if(!dirtyFields.date) date.text=fields.release_date || game.release_date || ""
        if(!dirtyFields.tags) tagText.text=(fields.tags || game.tags || []).join(", ")
        if(!dirtyFields.series) series.text=fields.series || game.series || ""
        if(!dirtyFields.category) category.currentIndex=Math.max(0,category.model.indexOf(fields.category || game.category || "其他"))
    }
    function resetSearch() { if(backend.coverSearchTarget==="enrichment:"+pane.record.id) backend.clearCoverSearch() }
    function search() { browserOpen=false;backend.searchTargetArtwork("enrichment",record.id,query.text,provider.currentValue,artKind,false) }
    onVisibleChanged: if(!visible) { browserOpen=false;backend.cancelArtworkSearch("enrichment",record.id || "") }
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
            AppComboBox { id: provider; objectName: "manualProvider"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 170; onCurrentIndexChanged: pane.resetSearch() }
            AppButton { objectName: "manualSearch"; text: "搜索图片与资料"; highlighted: true; enabled: !backend.busy && !!query.text.trim(); onClicked: pane.search() }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
            ScrollView {
                Layout.preferredWidth: Math.min(350,pane.width*.42); Layout.fillHeight: true; clip: true
                ColumnLayout {
                    width: parent.width-16; spacing: 8
                    Label { text: "补充缺失资料"; font.pixelSize: 17; font.weight: Font.DemiBold }
                    Label { text: "发行日期"; color: Theme.secondary }
                    AppTextField { id: date; objectName: "manualDate"; Layout.fillWidth: true; placeholderText: "YYYY-MM-DD"; enabled: pane.canFill("release_date"); onTextEdited: pane.mark("date") }
                    Label { text: "主分类"; color: Theme.secondary }
                    AppComboBox { id: category; Layout.fillWidth: true; model: backend.primaryCategories; enabled: pane.canFill("category"); onActivated: pane.mark("category") }
                    Label { text: "标签"; color: Theme.secondary }
                    AppTextField { id: tagText; objectName: "manualTags"; Layout.fillWidth: true; placeholderText: "逗号分隔，最多 6 个"; enabled: pane.canFill("tags"); onTextEdited: pane.mark("tags") }
                    Label { text: "系列"; color: Theme.secondary }
                    AppTextField { id: series; objectName: "manualSeries"; Layout.fillWidth: true; enabled: pane.canFill("series"); onTextEdited: pane.mark("series") }
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
                TabBar { id: imageKind; objectName: "manualImageKind"; Layout.fillWidth: true; onCurrentIndexChanged: pane.resetSearch(); TabButton { text: "封面" } TabButton { text: "横幅" } }
                Label { text: [pane.record.fields && pane.record.fields.cover ? "已选封面" : "",pane.record.fields && pane.record.fields.background ? "已选横幅" : ""].filter(Boolean).join(" / "); visible: !!text; color: Theme.accent; Layout.fillWidth: true }
                ProgressBar { visible: backend.artworkSearching && backend.coverSearchTarget==="enrichment:"+pane.record.id; indeterminate: true; Layout.fillWidth: true; Layout.preferredHeight: 3 }
                ArtworkResults {
                    id: candidates; objectName: "manualCandidates"; visible: !pane.browserOpen; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    targetKey: "enrichment:"+pane.record.id; completion: true; kind: pane.artKind
                    onChosen: function(ident,kind) { backend.previewEnrichmentArtwork(pane.record.id,ident,kind) }
                }
            }
        }
    }
}
