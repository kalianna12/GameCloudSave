import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls.Material
import "ControllerForm.js" as Form

ApplicationWindow {
    id: window
    objectName: "achievementsWindow"
    title: "成就管理";width: 1280;height: 880;minimumWidth: 900;minimumHeight: 650
    color: Theme.background;font.family: "Microsoft YaHei UI"
    Material.theme: Theme.dark ? Material.Dark : Material.Light;Material.accent: Theme.accent
    property var scopeIds: []
    property var selected: ({})
    readonly property var catalog: backend.achievements.overview
    readonly property var visibleGames: catalog.filter(function(g) {
        return g.supported && (!scopeIds.length || scopeIds.indexOf(g.id)>=0) && (!search.text || g.name.toLowerCase().indexOf(search.text.toLowerCase())>=0) &&
            (kind.currentIndex===0 || kind.currentIndex===1 && g.platform==="local" || kind.currentIndex===2 && g.platform==="steam" || kind.currentIndex===3 && !g.has_schema || kind.currentIndex===4 && !g.has_record || kind.currentIndex===5 && g.total>0 && g.unlocked===g.total)
    })
    function openFor(ids) { scopeIds=ids || [];backend.achievements.refreshCatalog();show();raise();requestActivate() }
    function selectGame(index) { if(index>=0 && index<visibleGames.length) { games.currentIndex=index;detail.loadFor(visibleGames[index].id) } }
    function choose(id,value) { var next=Object.assign({},selected);next[id]=value;selected=next }
    function selectVisible() { var next=Object.assign({},selected);visibleGames.forEach(function(g) { next[g.id]=true });selected=next }
    function start(force) {
        var ids=visibleGames.filter(function(g) { return selected[g.id] }).map(function(g) { return g.id })
        if(!ids.length) ids=visibleGames.map(function(g) { return g.id })
        if(ids.length) backend.achievements.batch(ids,backend.achievements.providers[provider.currentIndex].id,force)
    }
    function inside(item,parent) { while(item) { if(item===parent) return true;item=item.parent };return false }
    function controllerInput(command) {
        if(command==="back") { if(inside(window.activeFocusItem,detail)) games.forceActiveFocus();else close();return true }
        if(command==="menu") { if(detail.gameId) detail.save();return true }
        if(command==="previous" || command==="next") { selectGame(Math.max(0,Math.min(visibleGames.length-1,games.currentIndex+(command==="previous" ? -1 : 1))));return true }
        var focus=window.activeFocusItem
        if(inside(focus,detail)) return detail.controllerInput(command)
        if(games.activeFocus) {
            if(command==="up" || command==="down") { selectGame(Math.max(0,Math.min(visibleGames.length-1,games.currentIndex+(command==="up" ? -1 : 1))));games.positionViewAtIndex(games.currentIndex,ListView.Contain);return true }
            if(command==="favorite" && games.currentIndex>=0) { var g=visibleGames[games.currentIndex];choose(g.id,!selected[g.id]);return true }
            if(command==="right" || command==="activate") { if(!detail.gameId) selectGame(0);detail.controllerInput("down");return true }
            if(command==="left") { search.forceActiveFocus();return true }
            return true
        }
        if(command==="down" && focus===search) { games.forceActiveFocus();if(games.currentIndex<0) selectGame(0);return true }
        return Form.handle([gamesTab,sourcesTab,recentTab,search,kind,selectAll,provider,refresh,full,stop,save,closeButton],focus,command,null)
    }
    onVisibleGamesChanged: {
        if(!visibleGames.length) return
        var index=visibleGames.map(function(g) { return g.id }).indexOf(detail.gameId)
        games.currentIndex=index
    }
    ColumnLayout {
        anchors.fill: parent;anchors.margins: 24;spacing: 14
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                spacing: 4
                Label { text: "成就管理";font.pixelSize: 28;font.bold: true }
                Label { text: "游戏、成就与本地进度";color: Theme.secondary }
            }
            Item { Layout.fillWidth: true }
            Label { text: window.catalog.reduce(function(n,g) { return n+g.unlocked },0)+" / "+window.catalog.reduce(function(n,g) { return n+g.total },0)+" 已解锁";font.pixelSize: 18;color: Theme.accent }
            Label { text: window.catalog.filter(function(g) { return g.total>0 && g.unlocked===g.total }).length+" 款已完成";color: Theme.secondary }
            AppButton { id: closeButton;text: "关闭";onClicked: window.close() }
        }
        TabBar {
            id: pages;objectName: "achievementPages";Layout.fillWidth: true
            TabButton { id: gamesTab;text: "游戏与成就" }
            TabButton { id: sourcesTab;text: "数据源" }
            TabButton { id: recentTab;text: "最近解锁" }
        }
        RowLayout {
            visible: pages.currentIndex===0;Layout.fillWidth: true
            AppTextField { id: search;objectName: "achievementsLibrarySearch";Layout.fillWidth: true;placeholderText: "搜索游戏" }
            AppComboBox { id: kind;objectName: "achievementsLibraryFilter";model: ["全部游戏","本地游戏","Steam 游戏","尚未匹配","记录缺失","已完成"];Layout.preferredWidth: 140 }
            AppButton { id: selectAll;text: "全选当前结果";onClicked: window.selectVisible() }
        }
        RowLayout {
            visible: pages.currentIndex===0;Layout.fillWidth: true
            AppComboBox { id: provider;objectName: "achievementsBatchProvider";Layout.fillWidth: true;model: backend.achievements.providers;textRole: "name" }
            AppButton { id: refresh;objectName: "achievementsBatchStart";text: "补全缺失并检测记录";highlighted: true;enabled: !backend.achievements.batchState.running;onClicked: window.start(false) }
            AppButton { id: full;text: "重新匹配所选";enabled: !backend.achievements.batchState.running;onClicked: window.start(true) }
            AppButton { id: stop;text: "停止";enabled: backend.achievements.batchState.running;onClicked: backend.achievements.cancelBatch() }
        }
        ProgressBar { Layout.fillWidth: true;visible: backend.achievements.batchState.running;from: 0;to: Math.max(1,backend.achievements.batchState.total);value: backend.achievements.batchState.done }
        Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: backend.achievements.batchState.message;visible: !!text;color: Theme.secondary;font.pixelSize: 12 }
        RowLayout {
            visible: pages.currentIndex===0;Layout.fillWidth: true;Layout.fillHeight: true;spacing: 18
            ListView {
                id: games;objectName: "achievementsGameList";Layout.preferredWidth: window.width<1100 ? 230 : 290;Layout.fillHeight: true
                model: window.visibleGames;clip: true;spacing: 4;currentIndex: -1;reuseItems: true;boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: games.width;height: 101;radius: Theme.radius
                    color: games.currentIndex===index ? Theme.selection : Theme.surface;border.color: games.activeFocus && games.currentIndex===index ? Theme.accent : Theme.outline
                    TapHandler { onTapped: window.selectGame(index) }
                    CheckBox { id: checked;x: 2;y: 27;width: 38;checked: !!window.selected[modelData.id];onToggled: window.choose(modelData.id,checked) }
                    Column {
                        x: 45;y: 13;width: parent.width-58;spacing: 6
                        Label { width: parent.width;text: modelData.name;elide: Text.ElideRight;font.bold: true }
                        Label { width: parent.width;text: modelData.status+" · "+modelData.unlocked+"/"+modelData.total;elide: Text.ElideRight;color: modelData.has_record ? Theme.accent : Theme.secondary;font.pixelSize: 12 }
                        Label { width: parent.width;text: modelData.error || (modelData.platform==="steam" ? "Steam · " : "本地 · ")+"图标 "+modelData.icons_cached+"/"+modelData.icons_total;elide: Text.ElideRight;color: Theme.secondary;font.pixelSize: 11;ToolTip.text: modelData.error || text;ToolTip.visible: rowHover.hovered;HoverHandler { id: rowHover } }
                    }
                }
            }
            Rectangle { Layout.preferredWidth: 1;Layout.fillHeight: true;color: Theme.outline }
            Item {
                Layout.fillWidth: true;Layout.fillHeight: true
                AchievementsPane { id: detail;objectName: "achievementsLibraryDetail";anchors.fill: parent;visible: !!gameId }
                Label { visible: !detail.gameId;anchors.centerIn: parent;width: parent.width-30;text: "从左侧选择游戏，查看成就、数据源与记录检测详情。\n批量补全会复用已有列表，下载缺失图标；Steam 游戏只统计，不重复弹窗。";wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter;color: Theme.secondary }
            }
        }
        ScrollView {
            id: sourceView;visible: pages.currentIndex===1;Layout.fillWidth: true;Layout.fillHeight: true;clip: true;contentWidth: availableWidth
            ColumnLayout {
                width: sourceView.availableWidth;spacing: 18
                Label { text: "成就定义来源";font.pixelSize: 20;font.bold: true }
                Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "定义提供名称、说明与图标；解锁进度始终来自本机记录。自动模式先读取 Steam，失败时尝试已有本地定义和 SteamHunters。";color: Theme.secondary }
                Repeater {
                    model: [{name:"Steam",description:"按明确 App ID 获取公开成就定义，优先使用已有游戏平台 ID，不需要登录好友账号。"},{name:"SteamHunters",description:"按相同 Steam App ID 请求备用定义；无法访问时保留已有缓存，并在匹配结果中报告失败。"},{name:"本地定义 / Steam 缓存",description:"导入 JSON 定义，或读取 Steam 安装目录 appcache/stats 下的定义缓存。批量补全会复用已有数据，图标下载可断点续补。"}]
                    ColumnLayout {
                        required property var modelData;Layout.fillWidth: true;spacing: 7
                        Label { text: modelData.name;font.bold: true }
                        Label { text: modelData.description;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary }
                        Rectangle { Layout.fillWidth: true;implicitHeight: 1;color: Theme.outline }
                    }
                }
                Label { text: "本机进度来源";font.pixelSize: 20;font.bold: true }
                Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "Steam：从安装位置定位账号对应的 UserGameStats BIN，配对 Schema 解析位掩码。多个账号不会自动合并；Steam 游戏统计成就，但不显示本程序的解锁弹窗。\n\n本地游戏：检查游戏目录、已配置的存档目录、对应 App ID 的常见记录目录及手动添加的目录，读取 JSON / INI。没有记录的游戏不会凭列表伪造解锁。\n\n游戏页的“匹配与记录设置 → 检测详情”可查看已检查目录、未识别文件及原因。";color: Theme.secondary }
                Label { text: "开源参考：PlayniteAchievements · Justin Delano · MIT";color: Theme.secondary }
                AppButton { text: "查看上游项目";onClicked: Qt.openUrlExternally("https://github.com/justin-delano/PlayniteAchievements") }
            }
        }
        ListView {
            objectName: "achievementRecentList";visible: pages.currentIndex===2;Layout.fillWidth: true;Layout.fillHeight: true;clip: true;spacing: 6
            model: backend.achievements.recent;ScrollBar.vertical: ScrollBar {}
            delegate: Rectangle {
                required property var modelData;width: ListView.view.width;height: 78;color: Theme.surface;radius: Theme.radius
                RowLayout {
                    anchors.fill: parent;anchors.margins: 14;spacing: 14
                    Label { text: "★";font.pixelSize: 26;color: Theme.accent }
                    ColumnLayout { Layout.fillWidth: true;Label { text: modelData.name;font.bold: true } Label { text: modelData.game;color: Theme.secondary } }
                    Label { text: modelData.time;color: Theme.secondary }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: backend.controllerMode ? "LB / RB 切游戏 · X 勾选 · A 确认 · Menu 保存 · B 返回" : "成就定义与解锁记录分别检测；列表匹配成功不代表已找到记录。";Layout.fillWidth: true;color: Theme.secondary;font.pixelSize: 12;wrapMode: Text.Wrap }
            AppButton { id: save;text: "保存本游戏方案";visible: pages.currentIndex===0 && !!detail.gameId;enabled: !backend.achievements.state.busy;onClicked: detail.save() }
        }
    }
}
