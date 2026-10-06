import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    visible: true
    width: 1440; height: 940
    minimumWidth: 900; minimumHeight: 650
    title: "GameCloudSave · 第一版"
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
        gameCover.text = ""
        gameDialog.open()
    }
    function openSettings() {
        var s = backend.settings
        playnitePath.text = s.playnite; libraryPath.text = s.library
        snapshotPath.text = s.snapshots; rclonePath.text = s.rclone
        davUrl.text = s.dav_url; davUser.text = s.dav_user; davPassword.text = ""
        cloudPath.text = s.cloud_folder; cloudBrowsePath.text = s.cloud_folder
        watchSwitch.checked = s.watch
        aiSwitch.checked = s.ai_enabled; aiModel.text = s.ai_model; aiKey.text = ""
        settingsDialog.open()
    }
    function cloudValues() { return {dav_url: davUrl.text, dav_user: davUser.text, password: davPassword.text, rclone: rclonePath.text} }
    function saveLayout() { backend.saveSettings({cover_size:coverSize, columns:columnCount, gap:gridGap, installed_only:installedOnly}) }

    Rectangle {
        width: 94; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: "#161f19"
        Column {
            anchors.horizontalCenter: parent.horizontalCenter; y: 27; spacing: 28
            Image { source: "icons/app.svg"; width: 44; height: 44; anchors.horizontalCenter: parent.horizontalCenter }
            IconButton { iconName: "grid"; hint: "游戏库"; accent: true; width: 52; height: 48 }
            IconButton { iconName: "settings"; hint: "系统与本机设置"; width: 52; height: 48; onClicked: win.openSettings() }
        }
        Text { anchors.bottom: parent.bottom; anchors.bottomMargin: 30; anchors.horizontalCenter: parent.horizontalCenter; text: "V1"; color: "#738c7b"; font.pixelSize: 12 }
    }

    ColumnLayout {
        anchors { left: parent.left; leftMargin: 126; right: parent.right; rightMargin: 32; top: parent.top; topMargin: 28; bottom: parent.bottom; bottomMargin: 18 }
        spacing: 22
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Label { text: "GAMECLOUD / 你的游戏空间"; color: "#8ce34f"; font.pixelSize: 11; font.letterSpacing: 2 }
                Label { text: "我的游戏库"; font.pixelSize: 30; font.bold: true; color: "#f1f6f2" }
            }
            Item { Layout.fillWidth: true }
            TextField { id: search; objectName: "search"; placeholderText: "搜索游戏名称…"; Layout.preferredWidth: 230; selectByMouse: true }
            Button { text: "导入 Playnite"; enabled: !backend.busy; onClicked: backend.importGames() }
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
        RowLayout {
            Layout.fillWidth: true
            Label { text: "全部游戏"; font.pixelSize: 17; font.bold: true }
            Label { text: shownGames.length + " 个"; color: "#83988a" }
            CheckBox { text: "仅已安装"; checked: installedOnly; onToggled: { installedOnly = checked; saveLayout() } }
            Item { Layout.fillWidth: true }
            Label { text: "封面"; color: "#91a395" }
            Slider { from: 196; to: 300; value: coverSize; stepSize: 10; Layout.preferredWidth: 130; onMoved: coverSize = value; onPressedChanged: if (!pressed) saveLayout() }
            Label { text: "每行"; color: "#91a395" }
            SpinBox { from: 0; to: 10; value: columnCount; onValueModified: { columnCount = value; saveLayout() } textFromValue: function(v) { return v === 0 ? "自动" : v.toString() } valueFromText: function(t) { return t === "自动" ? 0 : parseInt(t) } }
            Label { text: "间隔"; color: "#91a395" }
            SpinBox { from: 8; to: 48; stepSize: 2; value: gridGap; onValueModified: { gridGap = value; saveLayout() } }
        }
        GridView {
            id: grid
            objectName: "gameGrid"
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            property int effectiveColumns: Math.max(1, Math.min(Math.floor(width / (196 + gridGap)), columnCount > 0 ? columnCount : Math.floor(width / (coverSize + gridGap))))
            cellWidth: width / effectiveColumns
            property real cardWidth: cellWidth - gridGap
            cellHeight: cardWidth * 1.38 + 108 + gridGap
            model: shownGames
            cacheBuffer: cellHeight
            ScrollBar.vertical: ScrollBar { }
            delegate: Rectangle {
                id: card
                required property var modelData
                width: grid.cardWidth; height: grid.cellHeight - gridGap
                radius: 12; color: hover.hovered ? "#25342a" : "#1c2720"
                border.color: hover.hovered ? "#56774f" : "#2b3930"
                Behavior on color { ColorAnimation { duration: 130 } }
                HoverHandler { id: hover }
                Rectangle {
                    id: poster
                    width: parent.width; height: grid.cardWidth * 1.38; radius: 12; color: "#2a3c2e"; clip: true
                    Image {
                        anchors.fill: parent; source: card.modelData.coverUrl; fillMode: Image.PreserveAspectCrop
                        asynchronous: true; sourceSize: Qt.size(Math.ceil(poster.width * 1.5), Math.ceil(poster.height * 1.5))
                    }
                    Label { visible: !card.modelData.coverUrl; anchors.centerIn: parent; width: parent.width - 26; text: card.modelData.name; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; color: "#9ed282"; font.pixelSize: 24; font.bold: true }
                    Rectangle {
                        x: 12; y: 12; width: badge.implicitWidth + 18; height: 24; radius: 6; color: "#dd17251a"
                        Label { id: badge; anchors.centerIn: parent; text: card.modelData.installed ? "已安装" : "未安装"; font.pixelSize: 10; color: card.modelData.installed ? "#b5f68b" : "#b6c1b8" }
                    }
                }
                Column {
                    x: 12; y: poster.height + 12; width: parent.width - 24; spacing: 7
                    Label { text: card.modelData.name; width: parent.width; elide: Text.ElideRight; color: "#f0f5f1"; font.pixelSize: 14; font.bold: true; ToolTip.visible: hover.hovered; ToolTip.text: text }
                    Label { text: card.modelData.saveSet ? "本机存档已配置" : "选择本机存档目录后可备份"; font.pixelSize: 10; color: card.modelData.saveSet ? "#a2c592" : "#8b9e90" }
                    Row {
                        spacing: Math.max(4, (parent.width - 160) / 3)
                        enabled: !backend.busy
                        IconButton { accent: true; iconName: "play"; hint: "启动"; onClicked: backend.launch(card.modelData.id) }
                        IconButton { iconName: "settings"; hint: "游戏本机设置"; onClicked: win.openGame(card.modelData) }
                        IconButton { iconName: "cloud"; hint: "云存档与快照历史"; onClicked: { selectGame(card.modelData); backend.history(activeId); historyDialog.open() } }
                        IconButton { iconName: "delete"; hint: "从管理列表移除"; onClicked: { selectGame(card.modelData); deleteDialog.open() } }
                    }
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
                Rectangle { Layout.fillWidth: true; height: 1; color: "#37483c" }
                Label { text: "云连接 · rclone WebDAV"; font.pixelSize: 19; font.bold: true }
                Label { text: "DAV 服务器地址" }
                TextField { id: davUrl; Layout.fillWidth: true; selectByMouse: true; placeholderText: "http://服务器:端口/dav/" }
                RowLayout {
                    TextField { id: davUser; placeholderText: "用户名"; Layout.fillWidth: true }
                    TextField { id: davPassword; placeholderText: backend.settings.has_password ? "密码已保存，留空保持" : "密码"; echoMode: TextInput.Password; Layout.fillWidth: true }
                }
                Label { text: "rclone 程序路径（每台电脑可单独设置）" }
                RowLayout { TextField { id: rclonePath; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFile("exe"); if(p) rclonePath.text=p } } }
                Label { text: "浏览云端文件夹" }
                RowLayout {
                    TextField { id: cloudBrowsePath; Layout.fillWidth: true; placeholderText: "留空浏览 DAV 根目录"; selectByMouse: true }
                    Button { text: "连接 / 浏览"; enabled: !backend.busy; onClicked: backend.browseCloud(cloudBrowsePath.text, win.cloudValues()) }
                    Button { text: "上一级"; enabled: !backend.busy; onClicked: { cloudBrowsePath.text = cloudBrowsePath.text.split('/').slice(0,-1).join('/'); backend.browseCloud(cloudBrowsePath.text, win.cloudValues()) } }
                }
                ListView {
                    Layout.fillWidth: true; Layout.preferredHeight: 110; clip: true
                    model: backend.directories
                    delegate: ItemDelegate {
                        required property var modelData
                        width: ListView.view.width; text: "▸  " + modelData.Name
                        onClicked: { cloudBrowsePath.text = (cloudBrowsePath.text ? cloudBrowsePath.text.replace(/\/$/, "") + "/" : "") + modelData.Name; backend.browseCloud(cloudBrowsePath.text, win.cloudValues()) }
                    }
                    ScrollBar.vertical: ScrollBar {}
                }
                Button { text: "选择当前文件夹"; enabled: !backend.busy; onClicked: cloudPath.text = cloudBrowsePath.text || "/" }
                Label { text: "所有游戏共用的云端根目录（自动按游戏 ID 分目录）" }
                TextField { id: cloudPath; Layout.fillWidth: true; selectByMouse: true }
                Rectangle { Layout.fillWidth: true; height: 1; color: "#37483c" }
                Label { text: "存档匹配 · DeepSeek"; font.pixelSize: 19; font.bold: true }
                Switch { id: aiSwitch; text: "使用 AI 对本地候选目录排序" }
                TextField { id: aiModel; Layout.fillWidth: true; placeholderText: "DeepSeek 模型名称" }
                TextField { id: aiKey; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "API Key 已保存，留空保持" : "DeepSeek API Key" }
                Label { text: "先扫描常见目录，AI 仅接收游戏名和候选文件夹名称；结果仍需手动确认。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#9db3a1" }
                Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#b7d4a8" }
            }
        }
        footer: DialogButtonBox {
            Button { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "保存本机设置"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: settingsDialog.close()
            onAccepted: {
                var values = win.cloudValues()
                values.playnite = playnitePath.text; values.library = libraryPath.text; values.snapshots = snapshotPath.text
                values.cloud_folder = cloudPath.text; values.watch = watchSwitch.checked
                values.ai_enabled = aiSwitch.checked; values.ai_model = aiModel.text; values.ai_key = aiKey.text
                backend.saveSettings(values); settingsDialog.close()
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
            Button { text: "查找常见存档候选目录"; enabled: !backend.busy; onClicked: backend.findSaves(activeId) }
            ComboBox { Layout.fillWidth: true; model: backend.candidates; onActivated: gameSave.text = currentText }
            Label { text: "启动 EXE（留空通过 Playnite 启动；启用进程监听时请填写）"; font.pixelSize: 12 }
            RowLayout { TextField { id: gameExe; Layout.fillWidth: true; selectByMouse: true } Button { text: "选择"; onClicked: { var p=backend.pickFile("exe"); if(p) gameExe.text=p } } }
            Label { text: "自定义封面（留空保持现有封面）" }
            RowLayout { TextField { id: gameCover; Layout.fillWidth: true } Button { text: "选择"; onClicked: { var p=backend.pickFile("cover"); if(p) gameCover.text=p } } }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#a3baaa" }
        }
        footer: DialogButtonBox {
            Button { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            Button { text: "保存"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: gameDialog.close()
            onAccepted: { backend.saveGame(activeId, {save_dir:gameSave.text, exe:gameExe.text, cover:gameCover.text}); gameDialog.close() }
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
