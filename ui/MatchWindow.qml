import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: matcher
    width: 1240; height: 860; minimumWidth: 960; minimumHeight: 700
    title: "AI 存档匹配 · 结果中心"; color: "#111a14"
    Material.theme: Material.Dark; Material.accent: "#8ce34f"
    font.family: "Microsoft YaHei UI"
    property string selectedId: ""
    signal cloudSetupRequested()
    function aiValues() { return {ai_enabled:enabledSwitch.checked,ai_model:modelName.text,ai_key:apiKey.text} }
    property var currentResult: backend.matchResults.find(function(r) { return r.id===matcher.selectedId }) || ({})
    function openMatcher(ident) {
        var s=backend.settings
        enabledSwitch.checked=s.ai_enabled; modelName.text=s.ai_model; apiKey.text=""
        if(ident) { selectedId=ident; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===ident }) }
        else if(!selectedId && backend.games.length) { selectedId=backend.matchResults.length ? backend.matchResults[0].id : backend.games[0].id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
        show(); raise(); requestActivate()
    }
    function label(state) { return state==="ready" ? "待自动备份" : state==="uploaded" ? "已上传" : state==="local_only" ? "本地已保存" : state==="saving" ? "本地备份中" : state==="uploading" ? "上传中" : state==="running" ? "匹配中" : state==="applied" ? "已设置" : state==="review" ? "待集中核对" : state==="notfound" ? "未找到" : state==="failed" ? "失败" : "未匹配" }
    onVisibleChanged: if(!visible) apiKey.text=""
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout {
            Label { text: "AI 存档匹配"; font.pixelSize: 28; font.bold: true }
            Label { text: "批量查找 → 验证存档 → 自动配置 → 本地备份 → 云端上传"; color: "#91ae99"; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 126; color: "#203729"; radius: 12
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 12; spacing: 5
                RowLayout {
                    Switch { id: enabledSwitch; text: "DeepSeek"; checked: backend.settings.ai_enabled }
                    TextField { id: modelName; Layout.preferredWidth: 175; placeholderText: "模型名称" }
                    TextField { id: apiKey; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "Key 已加密保存，留空保持" : "填写 API Key" }
                    Button { text: "保存并测试连接"; enabled: !backend.busy; onClicked: backend.testAi({ai_enabled:enabledSwitch.checked,ai_model:modelName.text,ai_key:apiKey.text}) }
                }
                Label { text: backend.aiConnection; color: "#a0d98c" }
                Label { text: "有明确存档文件证据的目录自动配置；多候选、共享目录及证据不足的结果集中核对。不会向 AI 发送存档内容。"; color: "#99ad9f"; font.pixelSize: 11; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
        }
        RowLayout {
            Button { text: "自动配置并备份云端 · 已安装游戏"; highlighted: true; enabled: !backend.busy; onClicked: { if(!backend.settings.cloud_folder) matcher.cloudSetupRequested(); else backend.autoWorkflow(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id }),true,matcher.aiValues()) } }
            Button { text: "自动配置并保存本地"; enabled: !backend.busy; onClicked: backend.autoWorkflow(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id }),false,matcher.aiValues()) }
            Button { text: "批量补传"; enabled: !backend.busy; onClicked: backend.retryAll() }
            Label { text: "云端位置："+(backend.settings.cloud_folder || "点击设置 DAV"); Layout.fillWidth: true; elide: Text.ElideRight; color: "#b2d39f"; TapHandler { onTapped: matcher.cloudSetupRequested() } HoverHandler { cursorShape: Qt.PointingHandCursor } }
        }
        RowLayout {
            ComboBox { id: selector; objectName: "matchGameSelector"; Layout.fillWidth: true; model: backend.games; textRole: "name"; valueRole: "id"; onActivated: matcher.selectedId=currentValue }
            Button { text: "匹配当前游戏"; enabled: !backend.busy && !!matcher.selectedId; onClicked: backend.matchGames([matcher.selectedId]) }
            Button { text: "匹配已安装游戏"; enabled: !backend.busy; onClicked: backend.matchGames(backend.games.filter(function(g) { return g.installed }).map(function(g) { return g.id })) }
            Button { text: "停止"; enabled: backend.matching; onClicked: backend.cancelMatching() }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 16
            Rectangle {
                Layout.preferredWidth: 310; Layout.fillHeight: true; radius: 12; color: "#1a281e"
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
                                Label { text: matcher.label(modelData.status)+"  ·  "+modelData.candidates.length+" 个候选"; color: modelData.status==="failed" ? "#f29c8e" : "#a8d98d"; font.pixelSize: 12 }
                            }
                        }
                        onClicked: { matcher.selectedId=modelData.id; selector.currentIndex=backend.games.findIndex(function(g) { return g.id===matcher.selectedId }) }
                    }
                    ScrollBar.vertical: ScrollBar {}
                    Label { visible: results.count===0; anchors.centerIn: parent; text: "还没有匹配记录"; color: "#92aa98" }
                }
            }
            ScrollView {
                id: detailsView
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                contentWidth: availableWidth
                ColumnLayout {
                    width: detailsView.availableWidth-14; spacing: 13
                    Label { text: matcher.currentResult.name || "选择游戏，开始匹配"; font.pixelSize: 22; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Label { text: matcher.label(matcher.currentResult.status)+" · "+(matcher.currentResult.model || "")+" · "+(matcher.currentResult.elapsed || 0)+" 秒"; color: "#9dcc91" }
                    Label { text: matcher.currentResult.message || "匹配结果会保存在本机，可随时重新查看。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: matcher.currentResult.status==="failed" ? "#f4a092" : "#aac2b0" }
                    Label { text: matcher.currentResult.ai_warning || ""; visible: !!text; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#e3c893" }
                    Label { text: "识别名称："+(matcher.currentResult.english_name || "—"); Layout.fillWidth: true; wrapMode: Text.Wrap }
                    Label { text: "别名："+(matcher.currentResult.aliases || []).join(" / "); Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a0b5a7" }
                    Label { text: matcher.currentResult.note || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#96aa9d"; visible: !!text }
                    Label { text: "已验证候选目录"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: matcher.currentResult.candidates || []
                        Rectangle {
                            required property var modelData
                            Layout.fillWidth: true; implicitHeight: candidateDetails.implicitHeight+24; radius: 10; color: "#23382a"
                            ColumnLayout {
                                id: candidateDetails
                                anchors.fill: parent; anchors.margins: 12; spacing: 8
                                Label { text: modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; font.bold: true }
                                Label { text: "参考置信度 "+Math.round(modelData.confidence*100)+"% · "+modelData.source; color: "#a6db8d"; font.pixelSize: 12 }
                                Label { text: modelData.reason; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a0b5a7" }
                                Label { text: "文件："+modelData.fileSummary; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#96aa9d"; font.pixelSize: 11 }
                                Button { text: "确认使用此存档目录"; enabled: !backend.busy; onClicked: backend.applyMatch(matcher.selectedId,modelData.path) }
                            }
                        }
                    }
                    Label { text: "模型建议目录核查"; font.pixelSize: 17; font.bold: true }
                    Repeater {
                        model: matcher.currentResult.checked || []
                        Label { required property var modelData; text: (modelData.exists ? "✓ 存在  " : "× 未找到  ")+modelData.path; Layout.fillWidth: true; wrapMode: Text.Wrap; color: modelData.exists ? "#a6d88f" : "#a4978c"; font.pixelSize: 12 }
                    }
                    Button { text: "匹配不到？手动选择存档目录"; enabled: !backend.busy && !!matcher.selectedId; onClicked: { var p=backend.pickFolder(""); if(p) backend.saveGame(matcher.selectedId,{save_dir:p}) } }
                }
            }
        }
        RowLayout {
            BusyIndicator { running: backend.busy; visible: running; implicitWidth: 26; implicitHeight: 26 }
            Label { text: backend.status; Layout.fillWidth: true; elide: Text.ElideRight; color: "#a7c4a3" }
            Button { text: "关闭"; onClicked: matcher.close() }
        }
    }
}
