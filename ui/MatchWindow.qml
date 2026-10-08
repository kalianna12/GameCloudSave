import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: matcher
    width: 1240; height: 860; minimumWidth: 960; minimumHeight: 700
    title: "查找存档"; color: "#1b1c1e"
    Material.theme: Material.Dark; Material.accent: "#80c942"
    font.family: "Microsoft YaHei UI"
    property string selectedId: ""
    property bool showConnection: !backend.settings.has_ai_key
    property bool showDetails: false
    signal cloudSetupRequested()
    function aiValues() { return {ai_enabled:enabledSwitch.checked,ai_model:modelName.text,ai_key:apiKey.text} }
    property var currentResult: backend.matchResults.find(function(r) { return r.id===matcher.selectedId }) || ({})
    function manualStartDirectory() {
        var candidates=currentResult.candidates || []
        if(candidates.length && candidates[0].path) return candidates[0].path
        var local=backend.gameSettings(selectedId)
        return local.save_dir || local.install_dir || ""
    }
    function openMatcher(ident) {
        var s=backend.settings
        enabledSwitch.checked=s.ai_enabled; modelName.text=s.ai_model; apiKey.text=""
        if(ident) { selectedId=ident; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===ident }) }
        else if(!selectedId && backend.games.length) { selectedId=backend.matchResults.length ? backend.matchResults[0].id : backend.games[0].id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
        show(); raise(); requestActivate()
    }
    function label(state) { return state==="ready" ? "可备份" : state==="uploaded" ? "已上传" : state==="local_only" ? "本地已保存" : state==="saving" ? "正在备份" : state==="uploading" ? "正在上传" : state==="running" ? "正在查找" : state==="applied" ? "已设置" : state==="review" ? "请确认目录" : state==="notfound" ? "未找到存档" : state==="failed" ? "失败" : "未查找" }
    onVisibleChanged: if(!visible) apiKey.text=""
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout {
            Label { text: "查找存档"; font.pixelSize: 28; font.bold: true }
            Item { Layout.fillWidth: true }
            AppButton { text: "匹配设置"; checkable: true; checked: matcher.showConnection; onToggled: matcher.showConnection=checked }
        }
        Rectangle {
            visible: matcher.showConnection
            Layout.fillWidth: true; Layout.preferredHeight: 126; color: "#27292c"; radius: 6
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 5
                RowLayout {
                    Switch { id: enabledSwitch; text: "DeepSeek"; checked: backend.settings.ai_enabled }
                    AppTextField { id: modelName; Layout.preferredWidth: 175; placeholderText: "模型名称" }
                    AppTextField { id: apiKey; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "Key 已加密保存，留空保持" : "填写 API Key" }
                    AppButton { text: "保存并测试连接"; enabled: !backend.busy; onClicked: backend.testAi({ai_enabled:enabledSwitch.checked,ai_model:modelName.text,ai_key:apiKey.text}) }
                }
                Label { text: backend.aiConnection; color: "#a6a9ae" }
                Label { text: "找到存档后可批量备份；无法确定的目录请手动选择。"; color: "#a6a9ae"; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        RowLayout {
            Label { text: "已安装游戏"; color: Theme.secondary; font.pixelSize: 12 }
            AppButton { text: "查找并备份到云端"; highlighted: true; enabled: !backend.busy; onClicked: { if(!backend.settings.cloud_folder) matcher.cloudSetupRequested(); else backend.autoWorkflow(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id }),true,matcher.aiValues()) } }
            AppButton { text: "查找并备份到本地"; enabled: !backend.busy; onClicked: backend.autoWorkflow(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id }),false,matcher.aiValues()) }
            AppButton { text: "批量补传"; enabled: !backend.busy; onClicked: backend.retryAll() }
            Label { text: "云端位置："+(backend.settings.cloud_folder || "点击设置 DAV"); Layout.fillWidth: true; elide: Text.ElideRight; color: "#a6a9ae"; TapHandler { onTapped: matcher.cloudSetupRequested() } HoverHandler { cursorShape: Qt.PointingHandCursor } }
        }
        RowLayout {
            ComboBox { id: selector; objectName: "matchGameSelector"; Layout.fillWidth: true; model: backend.games; textRole: "name"; valueRole: "id"; onActivated: matcher.selectedId=currentValue }
            AppButton { text: "匹配当前游戏"; enabled: !backend.busy && !!matcher.selectedId; onClicked: backend.matchGames([matcher.selectedId]) }
            AppButton { text: "匹配已安装游戏"; enabled: !backend.busy; onClicked: backend.matchGames(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id })) }
            AppButton { text: "停止"; enabled: backend.matching; onClicked: backend.cancelMatching() }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 16
            Rectangle {
                Layout.preferredWidth: 310; Layout.fillHeight: true; radius: 12; color: "#242629"
                ListView {
                    id: results; objectName: "matchResultList"
                    anchors.fill: parent; anchors.margins: 8; clip: true; model: backend.matchResults
                    delegate: ItemDelegate {
                        required property var modelData
                        width: ListView.view.width; height: 82; highlighted: modelData.id===matcher.selectedId
                        contentItem: ColumnLayout {
                            Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                            RowLayout {
                                BusyIndicator { implicitWidth: 20; implicitHeight: 20; running: ["running","saving","uploading"].indexOf(modelData.status)>=0; visible: running }
                                Label { text: matcher.label(modelData.status)+"  ·  "+modelData.candidates.length+" 个候选"; color: modelData.status==="failed" ? "#f29c8e" : "#a6a9ae"; font.pixelSize: 12 }
                            }
                        }
                        onClicked: { matcher.selectedId=modelData.id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
                    }
                    ScrollBar.vertical: ScrollBar {}
                    Label { visible: results.count===0; anchors.centerIn: parent; text: "还没有匹配记录"; color: "#a6a9ae" }
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
                    Label { visible: ["failed","notfound","local_only"].indexOf(matcher.currentResult.status)>=0; text: matcher.currentResult.message || "未找到存档，请手动选择目录。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: matcher.currentResult.status==="failed" ? "#f4a092" : Theme.secondary }
                    Label { text: matcher.currentResult.ai_warning || ""; visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#e3c893" }
                    Label { visible: matcher.showDetails; text: "游戏名称："+(matcher.currentResult.english_name || "—"); Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Label { visible: matcher.showDetails; text: "别名："+(matcher.currentResult.aliases || []).join(" / "); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { text: matcher.currentResult.note || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; visible: matcher.showDetails && !!text }
                    Label { text: "找到的目录"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: matcher.currentResult.candidates || []
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; implicitHeight: candidateDetails.implicitHeight+24; radius: 10; color: "#27292c"
                            ColumnLayout {
                                id: candidateDetails
                                anchors.fill: parent; anchors.margins: 12; spacing: 8
                                Label { text: modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true }
                                Label { visible: matcher.showDetails; text: "匹配度 "+Math.round(modelData.confidence*100)+"%"; color: Theme.secondary; font.pixelSize: 12 }
                                Label { visible: matcher.showDetails; text: modelData.reason || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                                Label { text: "文件："+modelData.fileSummary; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a6a9ae"; font.pixelSize: 11 }
                                AppButton { text: "使用此目录"; enabled: !backend.busy; onClicked: backend.applyMatch(matcher.selectedId,modelData.path) }
                            }
                        }
                    }
                    Label { visible: matcher.showDetails; text: "其他可能位置"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: matcher.showDetails ? matcher.currentResult.checked || [] : []
                        Label { required property var modelData; text: (modelData.exists ? "✓ 存在  " : "× 未找到  ")+modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; color: modelData.exists ? "#a6a9ae" : "#a4978c"; font.pixelSize: 12 }
                    }
                    AppButton { text: "手动选择目录"; enabled: !backend.busy && !!matcher.selectedId; onClicked: { var p=backend.pickSaveFolder(matcher.manualStartDirectory()); if(p) backend.saveGame(matcher.selectedId,{save_dir:p}) } }
                    AppButton { text: matcher.showDetails ? "收起详情" : "匹配详情"; checkable: true; checked: matcher.showDetails; onToggled: matcher.showDetails=checked }
                }
            }
        }
        RowLayout {
            BusyIndicator { running: backend.busy; visible: running; implicitWidth: 26; implicitHeight: 26 }
            Label { text: backend.status; Layout.fillWidth: true; elide: Text.ElideRight; color: "#a6a9ae" }
            AppButton { text: "关闭"; onClicked: matcher.close() }
        }
    }
}
