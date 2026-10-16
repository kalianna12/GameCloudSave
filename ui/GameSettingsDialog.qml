import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "gameDialog"
    property string gameId: ""
    readonly property var record: backend.games.find(function(game) { return game.id===dialog.gameId }) || ({})
    property bool dirty: false
    property var dirtyFields: ({})
    property string saving: ""
    signal cloudRequested()
    signal matchRequested(string ident)
    signal historyRequested(string ident)
    signal enrichmentRequested(string ident)
    title: (record.name || "游戏")+" · 游戏设置"
    modal: true; focus: true
    width: Math.min(900,parent.width-48); height: Math.min(820,parent.height-48)
    Overlay.modal: Rectangle { color: "#bb000000" }
    function loadLocalFields() {
        var local=backend.gameSettings(gameId)
        savePath.text=local.save_dir || "";exe.text=local.exe || "";monitor.text=local.monitor_exe || ""
        launchMode.currentIndex=Math.max(0,["direct","playnite","platform"].indexOf(local.launch_mode || (local.exe ? "direct" : "playnite")))
        gameArguments.text=local.arguments || "";working.text=local.working_dir || ""
    }
    function loadMetadata(keepDraft) {
        var game=backend.libraryMetadata(gameId)
        if(!keepDraft) dirtyFields=({})
        if(!dirtyFields.category) category.currentIndex=Math.max(0,category.model.indexOf(game.category || "其他"))
        if(!dirtyFields.tags) tags.text=(game.tags || []).join(", ")
        if(!dirtyFields.series) series.text=game.series || ""
        if(!dirtyFields.date) date.text=game.release_date || ""
        dirty=Object.keys(dirtyFields).length>0
    }
    function loadFields() { loadLocalFields();loadMetadata(false) }
    function mark(field) { var next=Object.assign({},dirtyFields);next[field]=true;dirtyFields=next;dirty=true }
    function openFor(ident,page) { gameId=ident;loadFields();tabs.currentIndex=page || 0;coverPicker.reset();saving="";open() }
    Connections {
        target: backend
        function onOperationCompleted(action,success) {
            if(!dialog.visible) return
            if(action===dialog.saving) { if(success) { if(action==="game-settings") dialog.loadLocalFields();else dialog.loadMetadata(false) };dialog.saving="" }
            else if(action==="enrichment-apply" && success) dialog.loadMetadata(true)
        }
    }
    contentItem: ColumnLayout {
        spacing: 14
        TabBar {
            id: tabs; objectName: "gameSettingsTabs"; Layout.fillWidth: true
            TabButton { text: "存档与云端" } TabButton { text: "封面与横幅" } TabButton { text: "游戏资料" }
        }
        ScrollView {
            visible: tabs.currentIndex===0; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ColumnLayout {
                width: dialog.availableWidth-20; spacing: 12
                Label { text: "本机存档目录"; font.bold: true }
                Label { text: "选择包含全部存档槽位的文件夹，程序会先保存本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                RowLayout {
                    AppTextField { id: savePath; objectName: "gameSavePath"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "尚未选择存档目录" }
                    AppButton { text: "选择目录"; enabled: !backend.busy; onClicked: { var path=backend.pickSaveFolder(savePath.text);if(path) savePath.text=path } }
                }
                RowLayout {
                    AppButton { text: "查找存档"; enabled: !backend.busy; onClicked: dialog.matchRequested(dialog.gameId) }
                    AppButton { text: "查看备份记录"; enabled: !backend.busy; onClicked: dialog.historyRequested(dialog.gameId) }
                }
                Label { text: backend.settings.watch ? "退出后自动备份已开启 · "+backend.watchInfo.message : "自动备份未开启，可在设置的备份页启用"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                RowLayout { Layout.fillWidth: true; AppTextField { id: monitor; Layout.fillWidth: true; placeholderText: "监听进程：自动识别，失败时指定实际游戏 EXE" } AppButton { text: "选择进程"; enabled: !backend.busy; onClicked: { var path=backend.pickFile("exe");if(path) monitor.text=path } } }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
                Label { text: "云端连接"; font.bold: true }
                Label { text: "所有游戏共用此连接。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                Label { text: backend.settings.dav_url || "尚未配置云端连接"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
                Label { text: "备份文件夹："+(backend.settings.cloud_folder || "尚未选择"); Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.secondary }
                AppButton { text: "设置 DAV 连接与文件夹"; enabled: !backend.busy; onClicked: dialog.cloudRequested() }
                Label { text: "AList 示例：http://服务器:5244/dav/，地址需以 /dav/ 结尾。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
                Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.border }
                AppButton { id: advanced; text: checked ? "收起启动与监听设置" : "启动与监听设置（无法识别进程时展开）"; checkable: true }
                ColumnLayout {
                    visible: advanced.checked; Layout.fillWidth: true; spacing: 10
                    Label { text: "启动方式" }
                    AppComboBox { id: launchMode; model: ["直接启动","通过 Playnite 启动","通过游戏平台启动"]; Layout.fillWidth: true }
                    RowLayout { AppTextField { id: exe; Layout.fillWidth: true; placeholderText: "启动文件 EXE / BAT / CMD" } AppButton { text: "选择"; enabled: !backend.busy; onClicked: { var path=backend.pickFile("exe");if(path) exe.text=path } } }
                    AppTextField { id: gameArguments; Layout.fillWidth: true; placeholderText: "启动参数（可选）" }
                    AppTextField { id: working; Layout.fillWidth: true; placeholderText: "工作目录（留空使用 EXE 所在目录）" }
                }
            }
        }
        CoverPicker { id: coverPicker; objectName: "gameCoverPicker"; visible: tabs.currentIndex===1; Layout.fillWidth: true; Layout.fillHeight: true; gameId: dialog.gameId; gameName: dialog.record.name || "" }
        ScrollView {
            visible: tabs.currentIndex===2; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            ColumnLayout {
                width: dialog.availableWidth-20; spacing: 12
                Label { text: "发行日期、分类、标签与系列"; font.pixelSize: 18; font.bold: true }
                Label { text: "可手动修改，也可先查询缺失资料，预览后再应用。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "查询这款游戏的缺失资料"; highlighted: true; enabled: !backend.busy; onClicked: dialog.enrichmentRequested(dialog.gameId) }
                Label { text: "发行日期（YYYY-MM-DD，未知时留空）" }
                AppTextField { id: date; objectName: "metadataDate"; Layout.fillWidth: true; onTextEdited: dialog.mark("date") }
                Label { text: dialog.dirtyFields.date ? "日期已编辑，保存后生效" : "日期来源："+(dialog.record.release_date_source || "未知"); color: Theme.secondary }
                Label { text: "主分类" }
                AppComboBox { id: category; Layout.fillWidth: true; model: backend.primaryCategories.concat(backend.groups.filter(function(name) { return backend.primaryCategories.indexOf(name)<0 })); onActivated: dialog.mark("category") }
                Label { text: "标签（逗号分隔，最多 6 个）" }
                AppTextField { id: tags; objectName: "metadataTags"; Layout.fillWidth: true; onTextEdited: dialog.mark("tags") }
                Label { text: dialog.dirtyFields.tags ? "标签已编辑，保存后生效" : "标签来源："+(dialog.record.tags_manual ? "手动" : dialog.record.tags_source || "未记录"); color: Theme.secondary }
                Label { text: "系列" }
                AppTextField { id: series; Layout.fillWidth: true; onTextEdited: dialog.mark("series") }
            }
        }
        RowLayout { AppBusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 } Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 } }
    }
    footer: Item {
        implicitHeight: 60
        RowLayout {
            anchors.fill: parent; anchors.margins: 10; spacing: 10
            Item { Layout.fillWidth: true }
            AppButton { text: "关闭"; onClicked: dialog.close() }
            AppButton { visible: tabs.currentIndex!==1; highlighted: true; text: tabs.currentIndex===0 ? "保存存档设置" : "保存游戏资料"; enabled: !backend.busy
                onClicked: {
                    if(tabs.currentIndex===0) { dialog.saving="game-settings";backend.saveGame(dialog.gameId,{save_dir:savePath.text,exe:exe.text,monitor_exe:monitor.text,launch_mode:["direct","playnite","platform"][launchMode.currentIndex],arguments:gameArguments.text,working_dir:working.text}) }
                    else { dialog.saving="library-edit";backend.updateLibrary([{id:dialog.gameId,category:category.currentText,tags:tags.text.split(/[,，]/).map(function(tag) { return tag.trim() }).filter(Boolean),series:series.text,release_date:date.text.trim()}]) }
                }
            }
        }
    }
}
