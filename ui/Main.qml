import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    visible: true
    width: 1440; height: 940
    minimumWidth: 900; minimumHeight: 650
    title: "GameCloudSave · V1.1"
    color: "#101612"
    Material.theme: Material.Dark
    Material.accent: "#8ce34f"
    Material.background: "#1b241e"
    Overlay.modal: Rectangle { color: "#bb070c08" }
    font.family: "Microsoft YaHei UI"
    property string activeId: ""
    property string activeName: ""
    property int coverSize: backend.settings.cover_size
    property int columnCount: backend.settings.columns
    property int gridGap: backend.settings.gap
    property bool installedOnly: backend.settings.installed_only
    property var shownGames: backend.games.filter(function(g) { return (!installedOnly || g.installed) && g.name.toLowerCase().indexOf(search.text.toLowerCase()) >= 0 })
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
        var s = backend.settings
        playnitePath.text = s.playnite; libraryPath.text = s.library
        snapshotPath.text = s.snapshots
        watchSwitch.checked=s.watch
        settingsDialog.open()
    }
    function openCloud() { cloudWindow.openBrowser() }
    function openMatch(ident) { matchWindow.openMatcher(ident || "") }
    function saveLayout() { backend.saveLayout({cover_size:coverSize, columns:columnCount, gap:gridGap, installed_only:installedOnly}) }
    CloudWindow { id: cloudWindow; objectName: "cloudWindow" }
    MatchWindow { id: matchWindow; objectName: "matchWindow" }


    Rectangle {
        width: 94; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: "#161f19"
        Column {
            anchors.horizontalCenter: parent.horizontalCenter; y: 27; spacing: 28
            Image { source: "icons/app.svg"; width: 44; height: 44; anchors.horizontalCenter: parent.horizontalCenter }
            IconButton { iconName: "grid"; hint: "游戏库"; accent: true; width: 52; height: 48 }
            IconButton { iconName: "settings"; hint: "系统与本机设置"; width: 52; height: 48; onClicked: win.openSettings() }
            IconButton { iconName: "cloud"; hint: "云端存储与文件浏览"; width: 52; height: 48; onClicked: win.openCloud() }
            IconButton { iconName: "spark"; hint: "AI 存档匹配"; width: 52; height: 48; onClicked: win.openMatch("") }
        }
        Text { anchors.bottom: parent.bottom; anchors.bottomMargin: 30; anchors.horizontalCenter: parent.horizontalCenter; text: "1.1"; color: "#738c7b"; font.pixelSize: 12 }
    }

    ColumnLayout {
        anchors { left: parent.left; leftMargin: 126; right: parent.right; rightMargin: 32; top: parent.top; topMargin: 28; bottom: parent.bottom; bottomMargin: 18 }
        spacing: 22
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Label { visible: win.width>=1100; text: "GAMECLOUD / 你的游戏空间"; color: "#8ce34f"; font.pixelSize: 11; font.letterSpacing: 2 }
                Label { text: "我的游戏库"; font.pixelSize: 30; font.bold: true; color: "#f1f6f2" }
            }
            Item { Layout.fillWidth: true }
            TextField { id: search; objectName: "search"; placeholderText: "搜索游戏…"; Layout.preferredWidth: win.width<1100 ? 130 : 200; selectByMouse: true }
            Button { text: "导入 Playnite"; enabled: !backend.busy; onClicked: backend.importGames() }
            Button { text: "云端存储"; onClicked: win.openCloud() }
            Button { text: "AI 匹配"; onClicked: win.openMatch("") }
            IconButton { iconName: "settings"; hint: "系统设置"; onClicked: win.openSettings() }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 125; radius: 16
            gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#244d2c" } GradientStop { position: 1; color: "#18271d" } }
            Column {
                x: 26; y: 23; spacing: 8
                Label { text: "每一段冒险，都值得保存。"; font.pixelSize: 24; font.bold: true; color: "#eff8ec" }
                Label { text: "本地快照先行  /  云端同步随后  /  每台电脑独立设置"; color: "#b4cdb7"; font.pixelSize: 13 }
            }
            Column {
                anchors.right: parent.right; anchors.rightMargin: 28; anchors.verticalCenter: parent.verticalCenter; spacing: 7
                Label { text: backend.games.length + " 款游戏"; font.pixelSize: 23; font.bold: true; color: "#d5fabd" }
                Label { text: backend.settings.computer; color: "#a8c2aa"; font.pixelSize: 12 }
            }
        }
        GridLayout {
            Layout.fillWidth: true; columns: win.width<1200 ? 1 : 2
            rowSpacing: 2; columnSpacing: 16
            RowLayout {
                Layout.fillWidth: true
                Label { text: "全部游戏"; font.pixelSize: 17; font.bold: true }
                Label { text: shownGames.length+" 个"; color: "#83988a" }
                CheckBox { text: "仅已安装"; checked: installedOnly; onToggled: { installedOnly=checked; saveLayout() } }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                Label { text: "封面"; color: "#91a395" }
                NodeSlider { objectName: "coverSlider"; value: coverSize; Layout.preferredWidth: win.width<1200 ? 180 : 220; onMoved: { coverSize=Math.round(value); columnCount=0 } onPressedChanged: if(!pressed) saveLayout() }
                Label { text: "每行"; color: "#91a395" }
                CompactSpinBox { from: 0; to: 10; value: columnCount; Layout.preferredWidth: 112; Layout.minimumWidth: 112; onValueModified: { columnCount=value; saveLayout() } textFromValue: function(v) { return v===0 ? "自动" : v.toString() } valueFromText: function(t) { return t==="自动" ? 0 : parseInt(t) } }
                Label { text: "间隔"; color: "#91a395" }
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
            cellHeight: cardWidth * 1.38 + 108 + gridGap
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
                Label { text: backend.games.length ? "没有匹配的游戏" : "把你的游戏带进来"; font.pixelSize: 25; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
                Label { text: "在系统设置确认 Playnite 程序与数据目录，然后点击导入。"; color: "#9db0a1" }
                Button { text: "设置本机路径"; anchors.horizontalCenter: parent.horizontalCenter; onClicked: win.openSettings() }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            BusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 }
            Rectangle { visible: !backend.busy; width: 6; height: 6; radius: 3; color: "#8ce34f" }
            Label { text: backend.status; color: "#a8bbad"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight; ToolTip.visible: statusHover.hovered; ToolTip.text: text; HoverHandler { id: statusHover } }
            Label { text: "LOCAL FIRST"; font.pixelSize: 10; color: "#67816f"; font.letterSpacing: 2 }
        }
    }

    Dialog {
        id: settingsDialog; objectName: "settingsDialog"; title: "系统设置 · " + backend.settings.computer
        anchors.centerIn: parent; width: Math.min(850, win.width - 70); height: Math.min(820, win.height - 60)
        modal: true
        Overlay.modal: Rectangle { color: "#bb070c08" }
        contentItem: ScrollView {
            clip: true
            ColumnLayout {
                width: settingsDialog.availableWidth - 20; spacing: 9
                Label { text: "本机配置  /  " + backend.settings.machine_id; color: "#8ce34f" }
                Label { text: "换电脑后，请在该电脑重新选择下面的路径与连接信息。"; color: "#a1b3a5" }
                Label { text: "Playnite 程序目录" }
                RowLayout { TextField { id: playnitePath; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFolder(playnitePath.text); if(p) playnitePath.text=p } } }
                Label { text: "Playnite 游戏库目录（包含 games.db 的 library 文件夹）" }
                RowLayout { TextField { id: libraryPath; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFolder(libraryPath.text); if(p) libraryPath.text=p } } }
                Label { text: "本地快照目录" }
                RowLayout { TextField { id: snapshotPath; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFolder(snapshotPath.text); if(p) snapshotPath.text=p } } }
                Switch { id: watchSwitch; text: "监听启动与退出（需要逐游戏设置启动 EXE 与存档目录）" }
                Button { text: "云端存储 · 连接 / 浏览 / 选择文件夹"; Layout.fillWidth: true; onClicked: win.openCloud() }
                Button { text: "AI 存档匹配 · 查看完整结果"; Layout.fillWidth: true; onClicked: win.openMatch("") }
                Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#b7d4a8" }
            }
        }
        footer: DialogButtonBox {
            Button { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "保存本机设置"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: settingsDialog.close()
            onAccepted: {
                backend.saveSettings({playnite:playnitePath.text, library:libraryPath.text, snapshots:snapshotPath.text, watch:watchSwitch.checked}); settingsDialog.close()
            }
        }
    }

    Dialog {
        id: gameDialog; objectName: "gameDialog"; title: activeName + " · 本机设置"; anchors.centerIn: parent
        width: 680; modal: true
        Overlay.modal: Rectangle { color: "#bb070c08" }
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: "这些路径只用于 " + backend.settings.computer; color: "#8ce34f" }
            Label { text: "存档目录" }
            RowLayout { TextField { id: gameSave; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFolder(gameSave.text); if(p) gameSave.text=p } } }
            Button { text: "打开 AI 匹配窗口 · 完整结果与失败原因"; onClicked: win.openMatch(activeId) }
            Label { text: "启动方式" }
            ComboBox { id: launchMode; Layout.fillWidth: true; model: ["直接启动 · 不打开 Playnite", "通过 Playnite · 保留启动脚本与插件动作"] }
            Label { text: "启动 EXE（直接启动时必须选择）"; font.pixelSize: 12 }
            RowLayout { TextField { id: gameExe; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFile("exe"); if(p) gameExe.text=p } } }
            TextField { id: gameArguments; Layout.fillWidth: true; placeholderText: "启动参数（可选）"; selectByMouse: true }
            RowLayout { TextField { id: gameWorking; Layout.fillWidth: true; placeholderText: "工作目录（留空使用 EXE 所在目录）"; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFolder(gameWorking.text); if(p) gameWorking.text=p } } }
            Label { text: "自定义封面（留空保持现有封面）" }
            RowLayout { TextField { id: gameCover; Layout.fillWidth: true } Button { text: "选择"; onClicked: { var p=backend.pickFile("cover"); if(p) gameCover.text=p } } }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a3baaa" }
        }
        footer: DialogButtonBox {
            Button { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "保存"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: gameDialog.close()
            onAccepted: { backend.saveGame(activeId, {save_dir:gameSave.text, exe:gameExe.text, cover:gameCover.text, launch_mode:launchMode.currentIndex===0 ? "direct" : "playnite", arguments:gameArguments.text, working_dir:gameWorking.text}); gameDialog.close() }
        }
    }
    Dialog {
        id: deleteDialog; title: "移除 " + activeName; anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb070c08" }
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "只移除管理条目，保留游戏文件和已有快照。" }
        onAccepted: backend.remove(activeId)
    }
    Dialog {
        id: historyDialog; objectName: "historyDialog"; title: activeName + " · 云存档"; anchors.centerIn: parent; width: 780; height: 530; modal: true
        Overlay.modal: Rectangle { color: "#bb070c08" }
        contentItem: ColumnLayout {
            RowLayout {
                IconButton { iconName: "cloud"; transferState: backend.transferStates[activeId] || "idle"; hoverEnabled: false; focusPolicy: Qt.NoFocus }
                Label { text: (backend.transferStates[activeId] || "idle")==="saving" ? "正在保存本地快照…" : backend.transferStates[activeId]==="uploading" ? "本地已保存，正在上传…" : backend.transferStates[activeId]==="success" ? "云端上传成功" : backend.transferStates[activeId]==="failed" ? "上传失败，本地快照保留，可补传" : "本地备份完成后再上传"; Layout.fillWidth: true; color: "#acd49b" }
            }
            RowLayout {
                enabled: !backend.busy
                Button { text: "保存本地 + 上传"; onClicked: backend.cloudSave(activeId) }
                Button { text: "仅本地备份"; onClicked: backend.localSave(activeId) }
                Button { text: "补传未上传快照"; onClicked: backend.retry(activeId) }
                Button { text: "刷新历史"; onClicked: backend.history(activeId) }
            }
            Label { text: "本机快照历史 · 恢复前会先备份当前存档"; color: "#9db3a3" }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; model: backend.snapshots; clip: true
                delegate: ItemDelegate {
                    required property var modelData
                    width: ListView.view.width; height: 72
                    contentItem: RowLayout {
                        ColumnLayout {
                            Layout.fillWidth: true
                            Label { text: modelData.created_at + "   #" + modelData.id }
                            Label { text: (modelData.uploaded ? "已上传" : "本地保存 / 待上传") + "  ·  " + modelData.note; color: "#91b27e"; font.pixelSize: 12 }
                        }
                        Button { text: "恢复"; enabled: !backend.busy; onClicked: { restoreDialog.snapshotId = modelData.id; restoreDialog.open() } }
                    }
                }
                ScrollBar.vertical: ScrollBar {}
            }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#bed9af" }
        }
        standardButtons: Dialog.Close
    }
    Dialog {
        id: restoreDialog; property int snapshotId: 0; anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb070c08" }
        title: "恢复快照 #" + snapshotId; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "将替换本机已配置目录中的存档。当前存档会先另行备份。" }
        onAccepted: backend.restore(activeId, snapshotId)
    }
}
