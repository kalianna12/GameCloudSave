import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

ApplicationWindow {
    id: window
    objectName: "enrichmentWindow"
    width: 1160; height: 820; minimumWidth: 900; minimumHeight: 650
    title: "资料补全"; color: Theme.background; font.family: "Microsoft YaHei UI"
    Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    property var scopeIds: []
    property var selected: ({})
    property bool hasQuery: false
    property bool ownsQuery: false
    property string queryScope: ""
    property string manualId: ""
    readonly property int candidateCount: backend.enrichmentResults.filter(function(row) { return !row.applied && Object.keys(row.fields).length>0 }).length
    ListModel { id: stableRows; dynamicRoles: true }
    AiSettingsDialog { id: aiSettings }
    function rowVisible(row) {
        if(onlyMissing.checked) return Object.keys(row.missing || {}).some(function(key) { return key!=="series" && row.missing[key] })
        return showAll.checked || !row.applied && Object.keys(row.fields).length>0
    }
    function sync() {
        var rows=backend.enrichmentResults.filter(rowVisible),next=Object.assign({},selected)
        for(var k=stableRows.count-1;k>=0;k--) if(!rows.some(function(row) { return row.id===stableRows.get(k).record.id })) stableRows.remove(k)
        for(var i=0;i<rows.length;i++) {
            var index=-1
            for(var j=0;j<stableRows.count;j++) if(stableRows.get(j).record.id===rows[i].id) { index=j;break }
            if(index<0) stableRows.append({record:rows[i]});else stableRows.set(index,{record:rows[i]})
            if(next[rows[i].id]===undefined) next[rows[i].id]=Object.keys(rows[i].fields).length>0
        }
        selected=next
    }
    function openFor(ids,options,autoStart) {
        if(backend.enrichmentProgress.running) { show();raise();requestActivate();return }
        var nextScope=JSON.stringify(ids || [])
        manualId=""
        if(nextScope!==queryScope) { stableRows.clear();selected=({});hasQuery=false;ownsQuery=false;queryScope=nextScope }
        scopeIds=ids || [];var values=options || {}
        dates.checked=values.dates!==false;tags.checked=values.tags!==false;covers.checked=values.covers!==false
        backgrounds.checked=values.backgrounds!==false
        ai.checked=values.use_ai!==undefined ? values.use_ai && backend.settings.has_ai_key : backend.settings.has_ai_key
        show();raise();requestActivate()
        if(autoStart) Qt.callLater(startQuery)
    }
    function startQuery() {
        if(backend.busy) return
        selected=({});stableRows.clear();hasQuery=true;ownsQuery=true
        backend.previewEnrichment(scopeIds,{dates:dates.checked,tags:tags.checked,covers:covers.checked,backgrounds:backgrounds.checked,use_ai:ai.checked})
    }
    function openManual(row) { if(backend.busy) return;manualId=row.id;backend.clearCoverSearch();manual.reset(row) }
    function ids() { return backend.enrichmentResults.filter(function(row) { return window.rowVisible(row) && !row.applied && window.selected[row.id] && Object.keys(row.fields).length>0 }).map(function(row) { return row.id }) }
    function selectCandidates() { var next={};backend.enrichmentResults.forEach(function(row) { next[row.id]=window.rowVisible(row) && !row.applied && Object.keys(row.fields).length>0 });selected=next }
    function describe(row) {
        var output=[],fields=row.fields,source=row.sources
        if(fields.release_date) output.push("发行日期："+fields.release_date+"（"+source.release_date+"）")
        if(fields.category) output.push("主分类："+fields.category+"（"+source.category+"）")
        if(fields.tags) output.push("标签："+fields.tags.join("、")+"（"+source.tags+"）")
        if(fields.series) output.push("系列："+fields.series+"（"+source.series+"）")
        if(fields.cover) output.push("封面："+(row.cover_name || row.name)+"（"+source.cover+"）")
        if(fields.background) output.push("横幅："+source.background)
        var names={release_date:"日期",category:"分类",tags:"标签",cover:"封面",background:"横幅"},missing=Object.keys(row.missing || {}).filter(function(key) { return key!=="series" && row.missing[key] }).map(function(key) { return names[key] })
        return (row.applied ? "已处理所选补全\n" : "")+(output.length ? output.join("\n") : missing.length ? "尚缺"+missing.join("、")+"，可手动搜索补全" : "现有资料完整")
    }
    Connections {
        target: backend
        function onEnrichmentChanged() { if(window.ownsQuery) window.sync() }
        function onOperationCompleted(action,success) {
            if(action==="enrichment-apply" && success && window.ownsQuery) { var next={};backend.enrichmentResults.forEach(function(row) { next[row.id]=false });window.selected=next }
            if(action==="ai-test" && success) ai.checked=true
            if(action==="enrichment-manual" && success && window.manualId) { var next=Object.assign({},window.selected);next[window.manualId]=true;window.selected=next;window.hasQuery=true;window.ownsQuery=true;window.sync();window.manualId="" }
            if(action==="enrichment-artwork" && success && window.manualId) { var next=Object.assign({},window.selected);next[window.manualId]=true;window.selected=next;var row=backend.enrichmentResults.find(function(r) { return r.id===window.manualId });if(row) manual.refreshProposal(row);window.sync() }
        }
    }
    onClosing: if(ownsQuery && backend.enrichmentProgress.running) backend.cancelEnrichment()
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 5
                Label { text: "资料补全"; font.pixelSize: 28; font.bold: true }
                Label { text: window.scopeIds.length ? "已选 "+window.scopeIds.length+" 款游戏" : "全部游戏"; color: Theme.secondary }
            }
            Item { Layout.fillWidth: true }
            AppButton { objectName: "enrichmentClose"; text: "关闭"; onClicked: window.close() }
        }
        Label { visible: !window.manualId; text: "只补缺失内容，查询后预览。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Flow {
            visible: !window.manualId; Layout.fillWidth: true; spacing: 12
            CheckBox { id: dates; text: "发行日期"; checked: true; enabled: !backend.busy }
            CheckBox { id: tags; text: "分类、标签与系列"; checked: true; enabled: !backend.busy }
            CheckBox { id: covers; text: "缺失封面"; checked: true; enabled: !backend.busy }
            CheckBox { id: backgrounds; objectName: "enrichBackgrounds"; text: "横幅背景"; checked: true; enabled: !backend.busy }
            CheckBox { id: ai; text: "DeepSeek 辅助识别与分类"; enabled: !backend.busy && backend.settings.has_ai_key; checked: backend.settings.has_ai_key }
        }
        RowLayout {
            visible: !window.manualId; Layout.fillWidth: true
            Label { visible: !backend.settings.has_ai_key; text: "未设置 DeepSeek Key"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            AppButton { text: "DeepSeek 设置"; enabled: !backend.busy; onClicked: aiSettings.openSettings() }
        }
        RowLayout {
            visible: !window.manualId; Layout.fillWidth: true
            AppButton { objectName: "startEnrichment"; text: window.hasQuery ? "重新查询缺失项" : "开始补全查询"; highlighted: true; enabled: !backend.busy && backend.games.length>0 && (dates.checked || tags.checked || covers.checked || backgrounds.checked); onClicked: window.startQuery() }
            AppButton { objectName: "stopEnrichment"; text: "停止查询"; visible: window.ownsQuery && backend.enrichmentProgress.running; enabled: backend.enrichmentProgress.phase.indexOf("正在停止")<0; onClicked: backend.cancelEnrichment() }
            Item { Layout.fillWidth: true }
            Label { text: window.hasQuery ? window.candidateCount+" 款可补全 / "+backend.enrichmentResults.length+" 款已处理" : "查询后在下方查看新增内容"; color: Theme.secondary }
        }
        ProgressBar { visible: window.ownsQuery && backend.enrichmentProgress.running; Layout.fillWidth: true; from: 0; to: Math.max(1,backend.enrichmentProgress.total); value: backend.enrichmentProgress.done; indeterminate: backend.enrichmentProgress.total===0 }
        Label { visible: window.hasQuery && backend.enrichmentProgress.running; text: backend.enrichmentProgress.phase; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
        RowLayout {
            visible: !window.manualId && window.hasQuery && backend.enrichmentResults.length>0; Layout.fillWidth: true
            AppButton { text: "选择可补全的游戏"; enabled: !backend.busy; onClicked: window.selectCandidates() }
            AppButton { text: "清除选择"; enabled: !backend.busy; onClicked: { var next={};backend.enrichmentResults.forEach(function(row) { next[row.id]=false });window.selected=next } }
            CheckBox { id: showAll; text: "显示全部查询结果"; checked: true; onToggled: if(window.ownsQuery) window.sync() }
            CheckBox { id: onlyMissing; objectName: "enrichOnlyMissing"; text: "仅显示缺失项"; onToggled: if(window.ownsQuery) window.sync() }
            Item { Layout.fillWidth: true }
            Label { text: "已选 "+window.ids().length+" 款"; color: Theme.secondary }
        }
        ListView {
            id: list; objectName: "enrichmentPreview"; visible: !window.manualId; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; spacing: 6; model: stableRows
            delegate: Rectangle {
                required property var record
                width: list.width; height: Math.max(140,row.implicitHeight+24); radius: 6; color: Theme.surface
                RowLayout {
                    id: row; anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 14
                    CheckBox { checked: !record.applied && !!window.selected[record.id]; enabled: !record.applied && !backend.busy && Object.keys(record.fields).length>0; onToggled: { var next=Object.assign({},window.selected);next[record.id]=checked;window.selected=next } }
                    ColumnLayout {
                        Layout.fillWidth: true; spacing: 6
                        Label { text: record.name; font.bold: true; font.pixelSize: 15; Layout.fillWidth: true; wrapMode: Text.Wrap }
                        Label { visible: !!record.matched_name && record.matched_name!==record.name; text: "资料匹配："+(record.matched_name || ""); color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11 }
                        Label { text: "查询时已有："+(record.before.release_date || "日期未知")+" / "+(record.before.category || "未分类")+" / "+(record.before.tags.length ? record.before.tags.join("、") : "未设置标签"); color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11 }
                        Label { text: window.describe(record); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Object.keys(record.fields).length ? Theme.text : Theme.secondary; font.pixelSize: 12 }
                        Label { visible: record.notes.length>0; text: record.notes.join("；"); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
                        AppButton { objectName: "manualEnrichment-"+record.id; text: "手动搜索与补全"; enabled: !backend.busy; onClicked: window.openManual(record) }
                    }
                    ColumnLayout {
                        visible: !!record.backgroundPreviewUrl || !!record.coverPreviewUrl || !!record.coverBeforeUrl
                        Layout.preferredWidth: 100; Layout.fillWidth: false
                        Image { source: record.coverPreviewUrl || record.coverBeforeUrl; asynchronous: true; fillMode: Image.PreserveAspectCrop; clip: true; Layout.preferredWidth: 86; Layout.preferredHeight: 120; sourceSize: Qt.size(258,360) }
                        Label { text: record.coverPreviewUrl ? "待补全封面" : "保留已有封面"; font.pixelSize: 10; color: Theme.secondary; Layout.alignment: Qt.AlignHCenter }
                        Image { visible: !!record.backgroundPreviewUrl; source: record.backgroundPreviewUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; clip: true; Layout.preferredWidth: 100; Layout.preferredHeight: visible ? 56 : 0; sourceSize.width: 300 }
                        Label { visible: !!record.backgroundPreviewUrl; text: "待补全横幅"; font.pixelSize: 10; color: Theme.secondary; Layout.alignment: Qt.AlignHCenter }
                    }
                }
            }
            ScrollBar.vertical: ScrollBar {}
            ColumnLayout {
                visible: list.count===0; anchors.centerIn: parent; width: Math.min(500,parent.width-40); spacing: 10
                Label { text: !backend.games.length ? "先导入游戏" : !window.hasQuery ? "从缺失的内容开始" : backend.enrichmentProgress.running ? "正在整理补全预览" : "没有待应用的补全内容"; font.pixelSize: 22; font.bold: true; Layout.alignment: Qt.AlignHCenter }
                Label { text: !backend.games.length ? "从游戏库的“导入游戏”添加游戏，再来补全资料。" : !window.hasQuery ? "勾选需要查询的内容，点击“开始补全查询”。现有日期、标签、系列和封面会自动跳过。" : backend.enrichmentProgress.running ? "查询会在后台运行，结果陆续显示。可以滚动预览或停止查询。" : "可勾选“显示全部查询结果”查看已有资料及未匹配原因。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; horizontalAlignment: Text.AlignHCenter }
            }
        }
        ManualEnrichmentPane { id: manual; visible: !!window.manualId; Layout.fillWidth: true; Layout.fillHeight: true; onBackRequested: window.manualId="" }
        RowLayout {
            Layout.fillWidth: true
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
            AppButton { objectName: "applyEnrichment"; visible: !window.manualId; text: "应用所选补全"; highlighted: true; enabled: !backend.busy && window.ownsQuery && window.ids().length>0; onClicked: backend.applyEnrichment(window.ids()) }
        }
    }
}
