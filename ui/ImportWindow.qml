import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: importer; width: 1060; height: 760; minimumWidth: 900; minimumHeight: 620
    title: "导入游戏"; color: Theme.background
    Material.theme: Material.Dark; Material.accent: "#80c942"; font.family: "Microsoft YaHei UI"
    property var selectedIds: ({})
    function platforms() { var output=[]; if(steam.checked) output.push("steam"); if(epic.checked) output.push("epic"); if(ubisoft.checked) output.push("ubisoft"); if(local.checked) output.push("local"); return output }
    function openImporter() { show(); raise(); requestActivate() }
    Connections { target: backend; function onChanged() {
        var next={}; backend.importCandidates.forEach(function(row) { if(importer.selectedIds[row.id]) next[row.id]=true }); importer.selectedIds=next
    } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "导入游戏"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: importer.close() } }
        TabBar { id: tabs; Layout.fillWidth: true; TabButton { text: "Playnite" } TabButton { text: "游戏平台" } TabButton { text: "扫描文件夹" } }
        Label { text: tabs.currentIndex===0 ? "读取 Playnite 游戏名称、封面和启动信息。重复导入保留存档设置。" : tabs.currentIndex===1 ? "读取本机已安装游戏，无需登录账号。未安装的账号游戏请先通过 Playnite 导入。" : "扫描 EXE、BAT、CMD 文件，不执行文件。每款游戏选择一个启动文件。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        RowLayout {
            visible: tabs.currentIndex<2
            CheckBox { id: steam; text: "Steam"; checked: true }
            CheckBox { id: epic; text: "Epic"; checked: true }
            CheckBox { id: ubisoft; text: "Ubisoft"; checked: true }
            CheckBox { id: local; text: "本地 / 其他"; checked: true; visible: tabs.currentIndex===0 }
            Item { Layout.fillWidth: true }
            AppButton { text: tabs.currentIndex===0 ? "导入所选平台" : "读取已安装游戏"; enabled: !backend.busy && importer.platforms().length>0; highlighted: true; onClicked: { if(tabs.currentIndex===0) backend.importPlaynitePlatforms(importer.platforms()); else { importer.selectedIds=({}); backend.previewPlatforms(importer.platforms()) } } }
        }
        RowLayout {
            visible: tabs.currentIndex===2; Layout.fillWidth: true
            AppTextField { id: folder; Layout.fillWidth: true; placeholderText: "选择包含多个游戏的文件夹" }
            AppButton { text: "选择文件夹"; onClicked: { var path=backend.pickFolder(folder.text); if(path) folder.text=path } }
            Label { text: "扫描层数"; color: Theme.secondary }
            CompactSpinBox { id: depth; from: 1; to: 10; value: 6 }
            AppButton { text: "扫描"; enabled: !backend.busy && !!folder.text; highlighted: true; onClicked: { importer.selectedIds=({}); backend.scanImports(folder.text,depth.value) } }
        }
        RowLayout {
            visible: tabs.currentIndex!==0
            AppButton { text: "全选"; enabled: !backend.busy; onClicked: { var next={}; var folders={}; backend.importCandidates.forEach(function(row) { if(!folders[row.install_dir]) { next[row.id]=true; folders[row.install_dir]=true } }); importer.selectedIds=next } }
            AppButton { text: "清除选择"; onClicked: importer.selectedIds=({}) }
            AppButton { text: "DeepSeek 辅助识别"; visible: tabs.currentIndex===2; enabled: !backend.busy && backend.settings.has_ai_key && backend.importCandidates.length>0; onClicked: backend.reviewImportLaunchers() }
            Label { text: "已选 "+Object.keys(importer.selectedIds).length+" 款"; color: Theme.secondary }
            Item { Layout.fillWidth: true }
            AppButton { text: "导入所选游戏"; enabled: !backend.busy && Object.keys(importer.selectedIds).length>0; onClicked: backend.importSelected(Object.keys(importer.selectedIds)) }
        }
        ListView {
            visible: tabs.currentIndex!==0; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: backend.importCandidates
            delegate: ItemDelegate {
                required property var modelData; width: ListView.view.width; height: 78
                contentItem: RowLayout {
                    CheckBox { checked: !!importer.selectedIds[modelData.id]; onToggled: { var next=Object.assign({},importer.selectedIds); if(checked) next[modelData.id]=true; else delete next[modelData.id]; importer.selectedIds=next } }
                    Image { source: "icons/"+modelData.platform+".svg"; Layout.preferredWidth: 24; Layout.preferredHeight: 24; sourceSize: Qt.size(72,72) }
                    ColumnLayout { Layout.fillWidth: true; spacing: 5
                        Label { text: modelData.name; font.bold: true }
                        Label { text: modelData.exe || modelData.install_dir; Layout.fillWidth: true; elide: Text.ElideMiddle; color: Theme.secondary; font.pixelSize: 11 }
                    }
                    ScoreRing { score: modelData.score; Layout.preferredWidth: 50; Layout.preferredHeight: 50 }
                }
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Item { visible: tabs.currentIndex===0; Layout.fillHeight: true }
        Label { visible: tabs.currentIndex===2; text: "规则先过滤常见安装器和工具。DeepSeek 只接收文件夹名与启动文件名，不读取文件内容；评分供选择参考。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
        RowLayout { BusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 } Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary } }
    }
}
