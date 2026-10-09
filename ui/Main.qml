import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    visible: true
    width: 1440; height: 940
    minimumWidth: 900; minimumHeight: 650
    title: "GameCloudSave · V1.8"
    color: "#1b1c1e"
    Material.theme: Material.Dark
    Material.accent: "#80c942"
    Material.background: "#27292c"
    Overlay.modal: Rectangle { color: "#bb000000" }
    font.family: "Microsoft YaHei UI"
    property string activeId: ""
    property string activeName: ""
    property int coverSize: backend.settings.cover_size
    property int columnCount: backend.settings.columns
    property int gridGap: backend.settings.gap
    property bool installedOnly: backend.settings.installed_only
    property string searchQuery: ""
    Timer { id: searchDelay; interval: 120; onTriggered: win.searchQuery=search.text.trim().toLowerCase() }
    property var shownGames: backend.games.filter(function(g) { return (!installedOnly || g.installed) && g.name.toLowerCase().indexOf(searchQuery) >= 0 })
    function selectGame(g) { activeId = g.id; activeName = g.name }
    function openGame(g) {
        selectGame(g)
        var v = backend.gameSettings(g.id)
        gameSave.text = v.save_dir || ""
        gameExe.text = v.exe || ""
        launchMode.currentIndex = (v.launch_mode || (v.exe ? "direct" : "playnite")) === "direct" ? 0 : 1
        gameArguments.text = v.arguments || ""
        gameWorking.text = v.working_dir || ""
        gameCover.text = ""
        gameDialog.open()
    }
    function openSettings() {
        guideDialog.close()
        var s = backend.settings
        playnitePath.text = s.playnite; libraryPath.text = s.library
        snapshotPath.text = s.snapshots
        watchSwitch.checked=s.watch
        autoUpload.checked=s.watch_upload
        settingsTabs.currentIndex=0
        settingsDialog.open()
    }
    function openCloud() { guideDialog.close(); cloudWindow.openBrowser() }
    function openMatch(ident) { guideDialog.close(); matchWindow.openMatcher(ident || "") }
    function saveLayout() { backend.saveLayout({cover_size:coverSize, columns:columnCount, gap:gridGap, installed_only:installedOnly}) }
    CloudWindow { id: cloudWindow; objectName: "cloudWindow" }
    MatchWindow { id: matchWindow; objectName: "matchWindow"; onCloudSetupRequested: win.openCloud() }
    Component.onCompleted: if(!backend.settings.guide_dismissed) guideDialog.open()


    Rectangle {
        width: 168; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: Theme.sidebar
        Row {
            x: 16; y: 24; spacing: 10
            Image { source: "icons/app.svg"; width: 28; height: 28; sourceSize: Qt.size(84,84) }
            Label { text: "GameCloudSave"; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 12; font.bold: true }
        }
        Column {
            x: 8; y: 84; spacing: 6
            NavigationButton { iconName: "grid"; text: "游戏库"; selected: true }
            NavigationButton { iconName: "cloud"; text: "云端存储"; onClicked: win.openCloud() }
            NavigationButton { iconName: "folder"; text: "查找存档"; onClicked: win.openMatch("") }
            NavigationButton { iconName: "folder"; text: "使用指南"; onClicked: guideDialog.open() }
        }
        NavigationButton { x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; iconName: "settings"; text: "设置"; onClicked: win.openSettings() }
    }

    ColumnLayout {
        anchors { left: parent.left; leftMargin: 200; right: parent.right; rightMargin: 32; top: parent.top; topMargin: 28; bottom: parent.bottom; bottomMargin: 18 }
        spacing: 18
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Label { text: "游戏库"; font.pixelSize: 24; font.bold: true; color: "#f0f1f2" }
            }
            Item { Layout.fillWidth: true }
            AppTextField { id: search; objectName: "search"; Keys.onEscapePressed: text=""; onTextChanged: searchDelay.restart(); placeholderText: "搜索游戏…"; Layout.preferredWidth: win.width<1100 ? 130 : 200; selectByMouse: true }
            AppButton { text: "导入 Playnite"; enabled: !backend.busy; onClicked: backend.importGames() }
        }
        GridLayout {
            Layout.fillWidth: true; columns: win.width<1200 ? 1 : 2
            rowSpacing: 2; columnSpacing: 16
            RowLayout {
                Layout.fillWidth: true
                Label { text: "全部游戏"; font.pixelSize: 17; font.bold: true }
                Label { text: shownGames.length+" 个"; color: "#a6a9ae" }
                CheckBox { text: "仅已安装"; checked: installedOnly; onToggled: { installedOnly=checked; saveLayout() } }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                Label { text: "封面"; color: "#a6a9ae" }
                NodeSlider { objectName: "coverSlider"; value: coverSize; Layout.preferredWidth: win.width<1200 ? 180 : 220; onMoved: { coverSize=Math.round(value); columnCount=0 } onPressedChanged: if(!pressed) saveLayout() }
                Label { text: "每行"; color: "#a6a9ae" }
                CompactSpinBox { from: 0; to: 10; value: columnCount; Layout.preferredWidth: 112; Layout.minimumWidth: 112; onValueModified: { columnCount=value; saveLayout() } textFromValue: function(v) { return v===0 ? "自动" : v.toString() } valueFromText: function(t) { return t==="自动" ? 0 : parseInt(t) } }
                Label { text: "间隔"; color: "#a6a9ae" }
                CompactSpinBox { from: 8; to: 48; stepSize: 2; value: gridGap; Layout.preferredWidth: 112; Layout.minimumWidth: 112; onValueModified: { gridGap=value; saveLayout() } }
                Item { Layout.fillWidth: win.width<1200 }
            }
        }
        GridView {
            id: grid
            objectName: "gameGrid"
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            property int effectiveColumns: Math.max(1, Math.min(Math.floor(width / (196 + gridGap)), columnCount > 0 ? columnCount : Math.floor(width / (coverSize + gridGap))))
            cellWidth: columnCount>0 ? width / effectiveColumns : Math.min(width,coverSize+gridGap)
            property real cardWidth: cellWidth - gridGap
            cellHeight: cardWidth * 1.38 + 120 + gridGap
            model: shownGames
            cacheBuffer: cellHeight*2
            reuseItems: true
            flickDeceleration: 2200
            maximumFlickVelocity: 3500
            ScrollBar.vertical: ScrollBar { }
            delegate: Item {
                required property var modelData
                width: grid.cellWidth; height: grid.cellHeight
                GameCard {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: grid.cardWidth; height: grid.cellHeight-gridGap
                    game: modelData; scrolling: grid.moving
                    transferState: backend.transferStates[modelData.id] || "idle"
                    onLaunchRequested: backend.launch(modelData.id)
                    onSettingsRequested: win.openGame(modelData)
                    onCloudRequested: { selectGame(modelData); backend.history(activeId); historyDialog.open() }
                    onRemoveRequested: { selectGame(modelData); deleteDialog.open() }
                }
            }
            Column {
                visible: grid.count === 0; anchors.centerIn: parent; spacing: 15
                Label { text: backend.games.length ? "没有匹配的游戏" : "尚未导入游戏"; font.pixelSize: 25; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
                Label { text: "从 Playnite 导入游戏，再选择需要备份的存档。"; color: "#a6a9ae" }
                AppButton { text: "设置本机路径"; anchors.horizontalCenter: parent.horizontalCenter; onClicked: win.openSettings() }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            BusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 }
            Rectangle { visible: !backend.busy; width: 6; height: 6; radius: 3; color: "#80c942" }
            Label { text: backend.status; color: "#a6a9ae"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight; ToolTip.visible: statusHover.hovered; ToolTip.text: text; HoverHandler { id: statusHover } }
        }
    }

    Dialog {
        id: guideDialog; objectName: "guideDialog"; title: "开始使用"
        anchors.centerIn: parent; width: Math.min(720,win.width-60); height: Math.min(730,win.height-60); modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: guideDialog.availableWidth-20; spacing: 16
                Label { text: "先导入游戏，再备份存档"; font.pixelSize: 22; font.bold: true }
                Label { text: "管理 Windows 游戏存档。封面和名称来自 Playnite，存档路径按当前电脑设置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                Label { text: "1. 导入游戏"; font.bold: true }
                Label { text: backend.games.length ? "已导入 "+backend.games.length+" 款游戏。新增游戏后可再次导入。" : "在设置里选择 Playnite 程序和 library 目录，保存后导入。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                RowLayout {
                    AppButton { text: "设置 Playnite 路径"; onClicked: { guideDialog.close(); win.openSettings() } }
                    AppButton { text: "导入游戏"; enabled: !backend.busy; onClicked: backend.importGames() }
                }
                Label { text: "2. 确认存档目录"; font.bold: true }
                Label { text: "先选一款玩过的游戏查找。核对候选目录，也可手动选择。多份存档应选择包含全部槽位的目录。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "查找存档"; enabled: backend.games.length>0; onClicked: { guideDialog.close(); win.openMatch("") } }
                Label { text: "3. 选择备份方式"; font.bold: true }
                Label { text: "游戏卡片的云朵按钮打开备份记录，可仅备份到本地。需要上传时，先设置 DAV 连接并选择云端文件夹；所有游戏共用这个位置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "设置云端存储（可选）"; onClicked: { guideDialog.close(); win.openCloud() } }
                Label { text: "4. 恢复存档"; font.bold: true }
                Label { text: "关闭游戏后，在备份记录中选择“恢复”。恢复前会先备份当前存档。记录列表显示本机快照，云端文件可在云端窗口浏览与下载。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                CheckBox { id: dismissGuide; text: "下次启动不再显示"; checked: backend.settings.guide_dismissed }
            }
        }
        footer: DialogButtonBox {
            AppButton { text: "进入游戏库"; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onAccepted: { backend.saveSettings({guide_dismissed:dismissGuide.checked}); guideDialog.close() }
        }
    }
    Dialog {
        id: settingsDialog; objectName: "settingsDialog"; title: "系统设置 · " + backend.settings.computer
        anchors.centerIn: parent; width: Math.min(850, win.width - 70); height: Math.min(600, win.height - 60)
        modal: true
        onRejected: { coverSize=backend.settings.cover_size; columnCount=backend.settings.columns; gridGap=backend.settings.gap; installedOnly=backend.settings.installed_only }
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: settingsDialog.availableWidth - 20; spacing: 9
                Label { text: "当前电脑：" + backend.settings.computer; color: Theme.secondary }
                TabBar {
                    id: settingsTabs; objectName: "settingsTabs"; Layout.fillWidth: true
                    TabButton { text: "游戏库" }
                    TabButton { text: "备份" }
                    TabButton { text: "显示" }
                    TabButton { text: "存档查找" }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===0; Layout.fillWidth: true; spacing: 10
                Label { text: "路径只用于当前电脑，换电脑后需重新选择。"; color: Theme.secondary }
                Label { text: "Playnite 程序目录" }
                RowLayout { AppTextField { id: playnitePath; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(playnitePath.text); if(p) playnitePath.text=p } } }
                Label { text: "Playnite 游戏库目录（包含 games.db 的 library 文件夹）" }
                RowLayout { AppTextField { id: libraryPath; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(libraryPath.text); if(p) libraryPath.text=p } } }
                Label { text: "保存设置后，在游戏库点击“导入 Playnite”。已有备份会保留。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===1; Layout.fillWidth: true; spacing: 10
                Label { text: "本地备份目录" }
                RowLayout { AppTextField { id: snapshotPath; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(snapshotPath.text); if(p) snapshotPath.text=p } } }
                Switch { id: watchSwitch; text: "游戏退出后自动备份" }
                CheckBox { id: autoUpload; text: "自动备份后上传云端"; enabled: watchSwitch.checked }
                Label { text: "自动备份需要在游戏设置中配置启动 EXE 和存档目录。上传失败会保留本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "设置云端连接与备份文件夹"; Layout.fillWidth: true; onClicked: win.openCloud() }
                Label { text: backend.settings.cloud_folder ? "云端文件夹："+backend.settings.cloud_folder : "尚未设置云端，可先使用本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                Label { text: "传输超时、重试次数和按电脑分目录，可在云端窗口的传输选项中设置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===2; Layout.fillWidth: true; spacing: 12
                Label { text: "修改后立即预览，点击保存保留布局。"; color: Theme.secondary }
                RowLayout { Label { text: "封面大小"; Layout.fillWidth: true } NodeSlider { value: coverSize; Layout.preferredWidth: 260; onMoved: { coverSize=Math.round(value); columnCount=0 } } }
                RowLayout { Label { text: "每行游戏数（0 为自动）"; Layout.fillWidth: true } CompactSpinBox { from: 0; to: 10; value: columnCount; onValueModified: columnCount=value } }
                RowLayout { Label { text: "卡片间距"; Layout.fillWidth: true } CompactSpinBox { from: 8; to: 48; stepSize: 2; value: gridGap; onValueModified: gridGap=value } }
                CheckBox { text: "仅显示已安装游戏"; checked: installedOnly; onToggled: installedOnly=checked }
                AppButton { text: "恢复默认布局"; onClicked: { coverSize=210; columnCount=0; gridGap=22; installedOnly=false } }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===3; Layout.fillWidth: true; spacing: 12
                Label { text: "查找 Windows 原生游戏存档，支持安装目录和用户目录中的多层路径。"; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Label { text: "联网查询、DeepSeek 和并行数量在查找窗口的“匹配设置”中调整。不使用 DeepSeek 也可以本地查找或手动选目录。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "打开存档查找与匹配设置"; Layout.fillWidth: true; onClicked: win.openMatch("") }
                Label { text: "目录存在不代表已有进度。未玩过的游戏可在首次保存后重新查找；多候选需要核对。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a6a9ae" }
            }
        }
        footer: DialogButtonBox {
            AppButton { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            AppButton { text: "保存本机设置"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: { coverSize=backend.settings.cover_size; columnCount=backend.settings.columns; gridGap=backend.settings.gap; installedOnly=backend.settings.installed_only; settingsDialog.close() }
            onAccepted: {
                backend.saveSettings({playnite:playnitePath.text, library:libraryPath.text, snapshots:snapshotPath.text, watch:watchSwitch.checked,watch_upload:autoUpload.checked}); saveLayout(); settingsDialog.close()
            }
        }
    }

    Dialog {
        id: gameDialog; objectName: "gameDialog"; title: activeName + " · 本机设置"; anchors.centerIn: parent
        width: Math.min(680,win.width-60); height: Math.min(780,win.height-60); modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
            width: gameDialog.availableWidth-20
            spacing: 12
            Label { text: "这些路径只用于 " + backend.settings.computer; color: "#80c942" }
            Label { text: "存档目录（包含所有存档槽）" }
            RowLayout { AppTextField { id: gameSave; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickSaveFolder(gameSave.text); if(p) gameSave.text=p } } }
            AppButton { text: "查找此游戏的存档"; onClicked: win.openMatch(activeId) }
            Label { text: "启动方式" }
            ComboBox { id: launchMode; Layout.fillWidth: true; model: ["直接启动", "通过 Playnite 启动"] }
            Label { text: "启动 EXE（直接启动时必须选择）"; font.pixelSize: 12 }
            RowLayout { AppTextField { id: gameExe; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFile("exe"); if(p) gameExe.text=p } } }
            AppTextField { id: gameArguments; Layout.fillWidth: true; placeholderText: "启动参数（可选）"; selectByMouse: true }
            RowLayout { AppTextField { id: gameWorking; Layout.fillWidth: true; placeholderText: "工作目录（留空使用 EXE 所在目录）"; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(gameWorking.text); if(p) gameWorking.text=p } } }
            Label { text: "自定义封面（留空保持现有封面）" }
            RowLayout { AppTextField { id: gameCover; Layout.fillWidth: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFile("cover"); if(p) gameCover.text=p } } }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a6a9ae" }
        }
        }
        footer: DialogButtonBox {
            AppButton { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            AppButton { text: "保存"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: gameDialog.close()
            onAccepted: { backend.saveGame(activeId, {save_dir:gameSave.text, exe:gameExe.text, cover:gameCover.text, launch_mode:launchMode.currentIndex===0 ? "direct" : "playnite", arguments:gameArguments.text, working_dir:gameWorking.text}); gameDialog.close() }
        }
    }
    Dialog {
        id: deleteDialog; title: "移除 " + activeName; anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "只移除管理条目，保留游戏文件和已有快照。" }
        onAccepted: backend.remove(activeId)
    }
    Dialog {
        id: historyDialog; objectName: "historyDialog"; title: activeName + " · 云存档"; anchors.centerIn: parent; width: 780; height: 530; modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ColumnLayout {
            RowLayout {
                IconButton { iconName: "cloud"; transferState: backend.transferStates[activeId] || "idle"; hoverEnabled: false; focusPolicy: Qt.NoFocus }
                Label { text: (backend.transferStates[activeId] || "idle")==="saving" ? "正在保存本地备份…" : backend.transferStates[activeId]==="uploading" ? "本地已保存，正在上传…" : backend.transferStates[activeId]==="success" ? "云端上传成功" : backend.transferStates[activeId]==="failed" ? "上传失败，本地备份保留，可补传" : "本地备份完成后再上传"; Layout.fillWidth: true; color: "#a6a9ae" }
            }
            RowLayout {
                enabled: !backend.busy
                AppButton { text: "保存本地 + 上传"; onClicked: backend.cloudSave(activeId) }
                AppButton { text: "仅本地备份"; onClicked: backend.localSave(activeId) }
                AppButton { text: "重试上传"; onClicked: backend.retry(activeId) }
                AppButton { text: "刷新历史"; onClicked: backend.history(activeId) }
            }
            Label { text: "本机备份记录 · 恢复前会先备份当前存档"; color: "#a6a9ae" }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; model: backend.snapshots; clip: true
                delegate: ItemDelegate {
                    required property var modelData
                    width: ListView.view.width; height: 72
                    contentItem: RowLayout {
                        ColumnLayout {
                            Layout.fillWidth: true
                            Label { text: modelData.created_at + "   #" + modelData.id }
                            Label { text: (modelData.uploaded ? "已上传" : "本地保存 / 待上传") + "  ·  " + modelData.note; color: "#a6a9ae"; font.pixelSize: 12 }
                        }
                        AppButton { text: "恢复"; enabled: !backend.busy; onClicked: { restoreDialog.snapshotId = modelData.id; restoreDialog.open() } }
                    }
                }
                ScrollBar.vertical: ScrollBar {}
                Label { visible: parent.count===0; anchors.centerIn: parent; text: "尚无本机备份，点击“仅本地备份”创建第一份。"; color: Theme.secondary }
            }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a6a9ae" }
        }
        standardButtons: Dialog.Close
    }
    Dialog {
        id: restoreDialog; property int snapshotId: 0; anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        title: "恢复快照 #" + snapshotId; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "将替换本机已配置目录中的存档。当前存档会先另行备份。" }
        onAccepted: backend.restore(activeId, snapshotId)
    }
}
