import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: importer; width: 1120; height: 800; minimumWidth: 900; minimumHeight: 650
    title: "导入游戏"; color: Theme.background; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent; font.family: "Microsoft YaHei UI"
    property var selectedIds: ({})
    property var orderedCandidates: backend.importCandidates.slice().sort(function(a,b) {
        var rankA=a.duplicate_id ? 2 : a.possible_duplicate ? 1 : 0,rankB=b.duplicate_id ? 2 : b.possible_duplicate ? 1 : 0
        if(rankA!==rankB) return rankA-rankB
        return importSort.currentIndex===2 ? b.score-a.score || a.name.localeCompare(b.name) : a.name.localeCompare(b.name)
    })
    onVisibleChanged: if(!visible) covers.hide()
    CoverWindow { id: covers }
    function platforms() { var output=[]; if(steam.checked) output.push("steam"); if(epic.checked) output.push("epic"); if(ubisoft.checked) output.push("ubisoft"); return output }
    function openImporter() { show(); raise(); requestActivate() }
    function selectAll() { var next={},folders={}; backend.importCandidates.forEach(function(row) { if(!row.duplicate_id && !row.possible_duplicate && !folders[row.install_dir || row.id]) { next[row.id]=true;folders[row.install_dir || row.id]=true } });selectedIds=next }
    Connections { target: backend; function onChanged() { var next={}; backend.importCandidates.forEach(function(row) { if(importer.selectedIds[row.id] && !row.duplicate_id) next[row.id]=true });importer.selectedIds=next } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 12
        RowLayout { Label { text: "导入游戏"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: importer.close() } }
        TabBar { id: tabs; objectName: "importTabs"; Layout.fillWidth: true; enabled: !backend.busy; onCurrentIndexChanged: { importer.selectedIds=({});backend.clearImportPreview() }
            TabButton { text: "Playnite 游戏库" } TabButton { text: "游戏平台" } TabButton { text: "本地文件夹" }
        }
        Label { text: tabs.currentIndex===0 ? "读取 Playnite 现成的游戏库和封面，预览后选择导入。" : tabs.currentIndex===1 ? "读取本机已安装游戏，排除 Playnite 和本软件已有的条目。" : "扫描启动文件，检查重复项，再选择游戏与封面。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        RowLayout { visible: tabs.currentIndex===0; Layout.fillWidth: true
            CheckBox { id: installedOnly; text: "仅已安装"; checked: true } Item { Layout.fillWidth: true }
            AppButton { text: "读取游戏库"; enabled: !backend.busy; highlighted: true; onClicked: backend.previewPlaynite(installedOnly.checked) }
        }
        RowLayout { visible: tabs.currentIndex===1; Layout.fillWidth: true
            CheckBox { id: steam; text: "Steam"; checked: true } CheckBox { id: epic; text: "Epic"; checked: true } CheckBox { id: ubisoft; text: "Ubisoft"; checked: true }
            Item { Layout.fillWidth: true } AppButton { text: "读取已安装游戏"; enabled: !backend.busy && importer.platforms().length>0; highlighted: true; onClicked: backend.previewPlatforms(importer.platforms()) }
        }
        RowLayout { visible: tabs.currentIndex===2; Layout.fillWidth: true
            AppTextField { id: folder; Layout.fillWidth: true; placeholderText: "选择包含游戏的文件夹" }
            AppButton { text: "选择"; enabled: !backend.busy; onClicked: { var path=backend.pickFolder(folder.text);if(path) folder.text=path } }
            Label { text: "层数"; color: Theme.secondary } CompactSpinBox { id: depth; from: 1; to: 10; value: 6 }
            AppButton { text: "扫描"; enabled: !backend.busy && !!folder.text; highlighted: true; onClicked: backend.scanImports(folder.text,depth.value) }
        }
        RowLayout {
            AppButton { text: "全选可导入项"; enabled: !backend.busy; onClicked: importer.selectAll() }
            AppButton { text: "清除选择"; onClicked: importer.selectedIds=({}) }
            ComboBox { id: importSort; Layout.preferredWidth: 150; model: ["新条目优先","名称排序","匹配分数"] }
            AppButton { text: "AI 检查名称与重复项"; visible: tabs.currentIndex===2; enabled: !backend.busy && backend.settings.has_ai_key && backend.importCandidates.length>0; onClicked: backend.reviewImportLaunchers() }
            Item { Layout.fillWidth: true } Label { text: "已选 "+Object.keys(importer.selectedIds).length+" 项"; color: Theme.secondary }
            AppButton { text: "导入所选"; enabled: !backend.busy && Object.keys(importer.selectedIds).length>0; highlighted: true; onClicked: { if(backend.importCandidates.some(function(row) { return importer.selectedIds[row.id] && row.possible_duplicate })) duplicateDialog.open();else backend.importSelected(Object.keys(importer.selectedIds)) } }
        }
        RowLayout { visible: tabs.currentIndex===2
            Label { text: "封面来源"; color: Theme.secondary } ComboBox { id: source; objectName: "coverSource"; model: backend.coverProviders; textRole: "label"; valueRole: "id"; Layout.preferredWidth: 210; Layout.minimumWidth: 190; currentIndex: Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===backend.settings.cover_source })) }
            CheckBox { id: aiCover; text: "AI 辅助名称匹配"; checked: backend.settings.ai_enabled; enabled: backend.settings.has_ai_key }
            AppButton { text: "为所选项匹配封面"; enabled: !backend.busy && Object.keys(importer.selectedIds).length>0 && (backend.coverProviders[source.currentIndex] || {}).kind!=="browser"; onClicked: backend.autoImportCovers(Object.keys(importer.selectedIds),source.currentValue,aiCover.checked) }
        }
        ListView { id: list; objectName: "importPreview"; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: importer.orderedCandidates; spacing: 3
            delegate: ItemDelegate {
                required property var modelData; width: ListView.view.width; height: 94
                contentItem: RowLayout {
                    CheckBox { checked: !!importer.selectedIds[modelData.id]; enabled: !backend.busy && !modelData.duplicate_id; onToggled: { var next=Object.assign({},importer.selectedIds);if(checked) { backend.importCandidates.forEach(function(row) { if(row.install_dir && row.install_dir===modelData.install_dir) delete next[row.id] });next[modelData.id]=true }else delete next[modelData.id];importer.selectedIds=next } }
                    Image { source: modelData.cover ? "file:///"+modelData.cover.replace(/\\/g,"/") : "icons/"+modelData.platform+".svg"; fillMode: Image.PreserveAspectFit; asynchronous: true; sourceSize: Qt.size(100,130); Layout.preferredWidth: 46; Layout.preferredHeight: 70 }
                    ColumnLayout { Layout.fillWidth: true; spacing: 4
                        Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                        Label { text: modelData.exe || modelData.install_dir || "未安装"; Layout.fillWidth: true; elide: Text.ElideMiddle; color: Theme.secondary; font.pixelSize: 11 }
                        Label { text: modelData.duplicate_reason || (modelData.possible_duplicate ? "可能重复："+modelData.possible_duplicate : modelData.cover_state || "可导入"); Layout.fillWidth: true; elide: Text.ElideRight; color: modelData.duplicate_id ? Theme.secondary : modelData.possible_duplicate ? "#e3c893" : Theme.accent; font.pixelSize: 11 }
                    }
                    AppButton { text: "搜索封面"; visible: !modelData.playnite; enabled: !backend.busy; onClicked: covers.openSearch("import",modelData.id,modelData.name,source.currentValue) }
                    ScoreRing { score: modelData.score; Layout.preferredWidth: 48; Layout.preferredHeight: 48 }
                }
            }
            ScrollBar.vertical: ScrollBar {}
            Label { visible: list.count===0; anchors.centerIn: parent; text: "读取或扫描后，在这里预览并选择游戏"; color: Theme.secondary }
        }
        RowLayout { BusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 } Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary } }
    }
    Dialog { id: duplicateDialog; title: "核对可能重复的游戏"; anchors.centerIn: parent; modal: true; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "所选项包含可能重复的游戏。确认它们是不同作品后再导入。" }
        onAccepted: backend.importSelected(Object.keys(importer.selectedIds))
    }
}
