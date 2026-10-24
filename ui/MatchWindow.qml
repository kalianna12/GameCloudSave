import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "SaveFilters.js" as SaveFilters
ApplicationWindow {
    ControlFocus {}
    id: matcher
    width: 1240; height: 860; minimumWidth: 960; minimumHeight: 700
    title: "查找存档"; color: Theme.background
    Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    font.family: "Microsoft YaHei UI"
    property string selectedId: ""
    property bool showConnection: !backend.settings.has_ai_key
    property bool showDetails: false
    property var followupIds: []
    property var scopeTargets: []
    function refreshTargets() { if(!searchScope || searchScope.currentIndex<0 || !installedScope) return;scopeTargets=backend.matchTargetIds(["pending","unsearched","all"][searchScope.currentIndex],installedScope.checked,followupIds) }
    function openForGames(ids) { openMatcher(ids.length ? ids[0] : "");searchScope.currentIndex=0;installedScope.checked=false;followupIds=ids;refreshTargets() }
    onFollowupIdsChanged: { if(searchScope) refreshTargets();syncResults() }
    ListModel { id: resultModel; dynamicRoles: true }
    function syncResults() {
        if(!results || !resultFilter || !resultQuery) return
        var savedY=results.contentY
        var rows=backend.matchResults.filter(function(row) { var game=backend.games.find(function(game) { return game.id===row.id }) || {};return (!matcher.followupIds.length || matcher.followupIds.indexOf(row.id)>=0) && SaveFilters.accept(row,resultFilter.currentIndex,!!game.saveSet,resultQuery.text) })
        for(var i=0;i<rows.length;i++) {
            var existing=-1
            for(var j=0;j<resultModel.count;j++) if(resultModel.get(j).record.id===rows[i].id) { existing=j; break }
            if(existing<0) resultModel.append({record:rows[i]})
            else resultModel.set(existing,{record:rows[i]})
        }
        for(var k=resultModel.count-1;k>=0;k--) if(!rows.some(function(r) { return r.id===resultModel.get(k).record.id })) resultModel.remove(k)
        Qt.callLater(function() { results.contentY=Math.max(results.originY,Math.min(savedY,Math.max(results.originY,results.contentHeight-results.height))) })
    }
    Component.onCompleted: syncResults()
    Connections { target: backend
        function onGamesChanged() { matcher.syncResults();matcher.refreshTargets() }
        function onMatchesChanged() { if(!backend.matching) { matcher.syncResults();matcher.refreshTargets() };matcher.currentResult=backend.matchResult(matcher.selectedId) }
        function onMatchRecordChanged(ident,row) {
            if(matcher.followupIds.length && matcher.followupIds.indexOf(ident)<0) return
            if(resultFilter.currentIndex!==0 || resultQuery.text) { matcher.syncResults();if(ident===matcher.selectedId) matcher.currentResult=row;return }
            var index=-1
            for(var i=0;i<resultModel.count;i++) if(resultModel.get(i).record.id===ident) { index=i;break }
            if(index<0) resultModel.append({record:row});else resultModel.set(index,{record:row})
            if(ident===matcher.selectedId) matcher.currentResult=row
        }
    }
    function openAiSettings() { openMatcher(""); showConnection=true }
    signal batchRequested()
    function aiValues() { return {ai_enabled:enabledSwitch.checked,ai_model:modelName.text,ai_key:apiKey.text,match_network:networkSwitch.checked,match_web_search:webSwitch.checked,match_ai_review:reviewSwitch.checked,match_ai_weight:aiWeight.value,match_workers:matchWorkers.value} }
    property var currentResult: ({})
    property int candidateLimit: 10
    onSelectedIdChanged: { currentResult=backend.matchResult(selectedId);candidateLimit=10 }
    function manualStartDirectory() {
        var candidates=currentResult.candidates || []
        if(candidates.length && candidates[0].path) return candidates[0].path
        var local=backend.gameSettings(selectedId)
        return local.save_dir || local.install_dir || ""
    }
    function openMatcher(ident) {
        followupIds=[]
        var s=backend.settings
        enabledSwitch.checked=s.ai_enabled; modelName.text=s.ai_model; apiKey.text=""
        networkSwitch.checked=s.match_network;reviewSwitch.checked=s.match_ai_review;matchWorkers.value=s.match_workers
        webSwitch.checked=s.match_web_search
        aiWeight.value=s.match_ai_weight
        if(ident) { selectedId=ident; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===ident }) }
        else if(!selectedId && backend.games.length) { selectedId=backend.matchResults.length ? backend.matchResults[0].id : backend.games[0].id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
        refreshTargets();show(); raise(); requestActivate()
    }
    function label(state) { return state==="ready" ? "可备份" : state==="uploaded" ? "已上传" : state==="local_only" ? "本地已保存" : state==="saving" ? "正在备份" : state==="uploading" ? "正在上传" : state==="running" ? "正在查找" : state==="applied" ? "已设置" : state==="review" ? "请确认目录" : state==="notfound" ? "未找到存档" : state==="failed" ? "失败" : "未查找" }
    onVisibleChanged: if(!visible) apiKey.text=""
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout {
            Label { text: "查找存档"; font.pixelSize: 28; font.bold: true }
            Item { Layout.fillWidth: true }
            AppButton { text: "DeepSeek / API Key"; checkable: true; checked: matcher.showConnection; onToggled: matcher.showConnection=checked }
            AppButton { text: "批量确认"; onClicked: matcher.batchRequested() }
        }
        Rectangle {
            visible: matcher.showConnection
            Layout.fillWidth: true; Layout.preferredHeight: 224; color: Theme.surface; radius: 6
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 5
                RowLayout {
                    Switch { id: enabledSwitch; text: "DeepSeek"; checked: backend.settings.ai_enabled }
                    AppTextField { id: modelName; Layout.preferredWidth: 175; placeholderText: "模型名称" }
                    AppTextField { id: apiKey; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "Key 已加密保存，留空保持" : "填写 API Key" }
                    AppButton { text: "保存并测试连接"; enabled: !backend.busy; onClicked: backend.testAi(matcher.aiValues()) }
                }
                RowLayout {
                    CheckBox { id: networkSwitch; text: "联网游戏资料"; checked: backend.settings.match_network }
                    CheckBox { id: reviewSwitch; text: "DeepSeek 辅助比较目录"; checked: backend.settings.match_ai_review }
                    Label { text: "并行游戏数" }
                    CompactSpinBox { id: matchWorkers; from: 1; to: 3; value: backend.settings.match_workers }
                    AppButton { text: "保存查找设置"; enabled: !backend.busy; onClicked: backend.saveSettings(matcher.aiValues()) }
                }
                RowLayout {
                    Label { text: "DeepSeek 权重" }
                    CompactSpinBox { id: aiWeight; objectName: "matchAiWeight"; from: 50; to: 95; stepSize: 5; value: backend.settings.match_ai_weight; enabled: enabledSwitch.checked && reviewSwitch.checked }
                    Label { text: "%   本地规则 "+(100-aiWeight.value)+"%"; color: Theme.secondary }
                    CheckBox { id: webSwitch; objectName: "matchWebSearch"; text: "未找到时网页深查"; checked: backend.settings.match_web_search; enabled: networkSwitch.checked && enabledSwitch.checked }
                    Item { Layout.fillWidth: true }
                }
                Label { text: backend.aiConnection; color: Theme.secondary }
            }
        }
        RowLayout {
            AppComboBox { id: selector; objectName: "matchGameSelector"; Layout.fillWidth: true; model: backend.games; textRole: "name"; valueRole: "id"; onActivated: { matcher.selectedId=currentValue;if(matcher.followupIds.length && matcher.followupIds.indexOf(currentValue)<0) matcher.followupIds=[] } }
            AppButton { text: "查找当前游戏"; enabled: !backend.busy && !!matcher.selectedId; onClicked: backend.matchGames([matcher.selectedId],matcher.aiValues()) }
            AppButton { objectName: "findScopedSaves";text: "查找此范围"; enabled: !backend.busy && matcher.scopeTargets.length>0; onClicked: backend.matchGames(matcher.scopeTargets,matcher.aiValues()) }
            AppButton { objectName: "findAllSaves";text: "重新查找全部"; enabled: !backend.busy && backend.games.length>0;onClicked: { matcher.followupIds=[];backend.matchGames(backend.matchTargetIds("all",false,[]),matcher.aiValues()) } }
            AppButton { objectName: "stopMatching"; text: backend.matchProgress.cancelled ? "正在停止" : "停止"; enabled: backend.matching && !backend.matchProgress.cancelled; onClicked: backend.cancelMatching() }
        }
        RowLayout {
            Layout.fillWidth: true
            AppComboBox { id: searchScope;objectName: "saveSearchScope";Layout.preferredWidth: 250;model: ["待处理：未查找优先，跳过已设置","仅从未查找","重新查找（含已设置）"];onCurrentIndexChanged: if(installedScope) matcher.refreshTargets() }
            CheckBox { id: installedScope;objectName: "saveSearchInstalled";text: "仅已安装";checked: true;onToggled: matcher.refreshTargets() }
            Label { text: (matcher.followupIds.length ? "所选后续 · " : "")+matcher.scopeTargets.length+" 款；当前游戏可随时单独重查";Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;font.pixelSize: 12 }
        }
        ColumnLayout {
            visible: backend.matching; Layout.fillWidth: true; spacing: 6
            RowLayout {
                Label { text: backend.matchProgress.done+" / "+backend.matchProgress.total+" 款游戏"; color: Theme.text }
                Label { text: backend.matchProgress.phase; Layout.fillWidth: true; color: Theme.secondary; elide: Text.ElideRight; font.pixelSize: 12 }
            }
            ProgressBar { objectName: "matchProgressBar"; Layout.fillWidth: true; indeterminate: backend.matching && backend.matchProgress.done===0; from: 0; to: Math.max(1,backend.matchProgress.total); value: backend.matchProgress.done }
        }
        RowLayout {
            AppTextField { id: resultQuery; objectName: "matchResultQuery"; Layout.fillWidth: true; placeholderText: "筛选游戏名称或别名"; onTextChanged: matcher.syncResults() }
            AppComboBox { id: resultFilter; objectName: "matchResultFilter"; Layout.preferredWidth: 190; model: ["全部结果","未设置目录","未找到候选","待确认目录","已设置目录","备份或上传失败"]; onCurrentIndexChanged: matcher.syncResults() }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 16
            Rectangle {
                Layout.preferredWidth: 270; Layout.fillHeight: true; radius: 6; color: Theme.sidebar
                ListView {
                    id: results; objectName: "matchResultList"
                    anchors.fill: parent; anchors.margins: 8; clip: true; model: resultModel
                    delegate: ItemDelegate {
                        required property var record
                        property var modelData: record
                        width: ListView.view.width; height: 70; highlighted: modelData.id===matcher.selectedId
                        contentItem: ColumnLayout {
                            Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                            RowLayout {
                                AppBusyIndicator { implicitWidth: 20; implicitHeight: 20; running: ["running","saving","uploading"].indexOf(modelData.status)>=0; visible: running }
                                Label { text: matcher.label(modelData.status)+"  ·  "+modelData.candidates.length+" 个候选"; color: modelData.status==="failed" ? "#f29c8e" : Theme.secondary; font.pixelSize: 12 }
                            }
                        }
                        onClicked: { matcher.selectedId=modelData.id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
                    }
                    ScrollBar.vertical: ScrollBar {}
                    Label { visible: results.count===0; anchors.centerIn: parent; text: "还没有匹配记录"; color: Theme.secondary }
                }
            }
            ScrollView {
                id: detailsView
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: detailsView.availableWidth-14; spacing: 13
                    Label { text: matcher.currentResult.name || "选择游戏，开始匹配"; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Label { text: matcher.label(matcher.currentResult.status); color: Theme.secondary }
                    Label { visible: !!matcher.currentResult.candidates && matcher.currentResult.candidates.length>0 && matcher.currentResult.scan_version!==4;text: "这是旧版文件识别结果，建议重新查找当前游戏以更新进度文件与评分。";Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary }
                    Label { visible: ["failed","notfound","local_only"].indexOf(matcher.currentResult.status)>=0; text: matcher.currentResult.message || "未找到存档，请手动选择目录。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: matcher.currentResult.status==="failed" ? "#f4a092" : Theme.secondary }
                    Label { text: matcher.currentResult.ai_warning || ""; visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#e3c893" }
                    Label { text: matcher.currentResult.network_warning || ""; visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { text: "开发商："+(matcher.currentResult.developers || []).join(" / "); visible: !!(matcher.currentResult.developers || []).length; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { text: (matcher.currentResult.scan_modes || []).map(function(mode) { return (mode.mode==="local" ? "本地" : mode.mode==="network" ? "Steam 资料" : mode.mode==="web" ? "网页初查" : mode.mode==="web-deep" ? "网页二次深查" : "DeepSeek")+"："+(mode.state==="done" ? "完成" : mode.state==="running" ? "查询中" : "暂不可用") }).join("   "); visible: matcher.showDetails && !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
                    Label { text: matcher.currentResult.web_warning || ""; visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { visible: matcher.showDetails; text: "游戏名称："+(matcher.currentResult.english_name || "—"); Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Label { visible: matcher.showDetails; text: "别名："+(matcher.currentResult.aliases || []).join(" / "); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { text: matcher.currentResult.note || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; visible: matcher.showDetails && !!text }
                    Label { text: "找到的目录"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: (matcher.currentResult.candidates || []).slice(0,matcher.candidateLimit)
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; implicitHeight: Math.max(candidateDetails.implicitHeight+32,128); radius: 6; color: Theme.surface
                            border.color: "#35383c"
                            ScoreRing { anchors.right: parent.right; anchors.rightMargin: 16; anchors.top: parent.top; anchors.topMargin: 16; score: modelData.confidence }
                            ColumnLayout {
                                id: candidateDetails
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 16; rightMargin: 96 }
                                spacing: 8
                                Label { text: modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true }
                                Label { visible: matcher.showDetails; text: "匹配评分 "+Math.round(modelData.confidence*100)+" / 100"; color: Theme.secondary; font.pixelSize: 12 }
                                Label { visible: matcher.showDetails; text: modelData.reason || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                                Label { visible: matcher.showDetails && modelData.ai_confidence!==undefined; text: "本地 "+Math.round((modelData.local_confidence!==undefined ? modelData.local_confidence : modelData.confidence)*100)+" 分 / DeepSeek "+Math.round((modelData.ai_confidence || 0)*100)+" 分 · DeepSeek 权重 "+Math.round((modelData.ai_weight || 0)*100)+"%\n"+(modelData.ai_reason || ""); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                                Label { visible: matcher.showDetails && !!modelData.score_details; text: modelData.score_details ? "开发商目录："+(modelData.score_details.developer_match ? "匹配" : "未确认")+" / 进度文件："+(modelData.has_save_evidence ? "已核验" : "未核验") : ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
                                Label { text: "文件："+modelData.fileSummary; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
                                Label { visible: !!modelData.score_note;text: modelData.score_note || "";Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.accent;font.pixelSize: 12 }
                                Label { text: "尚未确认实际进度文件，请核对后使用"; visible: modelData.has_save_evidence===false; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
                                RowLayout {
                                    AppButton { text: matcher.currentResult.applied_path===modelData.path ? "已使用" : "使用此目录"; enabled: !backend.busy && matcher.currentResult.applied_path!==modelData.path; onClicked: backend.applyMatch(matcher.selectedId,modelData.path) }
                                }
                            }
                        }
                    }
                    Label { visible: matcher.showDetails; text: "其他可能位置"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: matcher.showDetails ? matcher.currentResult.checked || [] : []
                        Label { required property var modelData; text: (modelData.exists ? "✓ 存在  " : "× 未找到  ")+modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; color: modelData.exists ? Theme.secondary : "#a4978c"; font.pixelSize: 12 }
                    }
                    AppButton { visible: (matcher.currentResult.candidates || []).length>matcher.candidateLimit; text: "显示更多目录"; onClicked: matcher.candidateLimit+=10 }
                    AppButton { text: "手动选择目录"; enabled: !backend.busy && !!matcher.selectedId; onClicked: { var p=backend.pickSaveFolder(matcher.manualStartDirectory()); if(p) backend.saveGame(matcher.selectedId,{save_dir:p}) } }
                    AppButton { text: matcher.showDetails ? "收起详情" : "匹配详情"; checkable: true; checked: matcher.showDetails; onToggled: matcher.showDetails=checked }
                    Repeater {
                        model: matcher.showDetails ? matcher.currentResult.sources || [] : []
                        Label { required property var modelData; text: "资料来源："+modelData.title; color: Theme.secondary; Layout.fillWidth: true; elide: Text.ElideRight; TapHandler { onTapped: { if(/^https?:\/\//.test(modelData.url)) Qt.openUrlExternally(modelData.url) } } HoverHandler { cursorShape: Qt.PointingHandCursor } }
                    }
                }
            }
        }
        RowLayout {
            AppBusyIndicator { running: backend.busy; visible: running; implicitWidth: 26; implicitHeight: 26 }
            Label { text: backend.status; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary }
            AppButton { text: "关闭"; onClicked: matcher.close() }
        }
    }
}
