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
    property string chartGame: ""
    property int chartDays: 30
    property bool cumulative: false
    readonly property var chartStatistics: { var revision=backend.achievements.summaryRevision;return backend.achievements.statistics(chartGame,chartDays) }
    readonly property var catalog: backend.achievements.overview
    readonly property var visibleGames: catalog.filter(function(g) {
        return g.supported && (!scopeIds.length || scopeIds.indexOf(g.id)>=0) && (!search.text || g.name.toLowerCase().indexOf(search.text.toLowerCase())>=0) &&
            (kind.currentIndex===0 || kind.currentIndex===1 && g.platform==="local" || kind.currentIndex===2 && g.platform==="steam" || kind.currentIndex===3 && !g.has_schema || kind.currentIndex===4 && !g.has_record || kind.currentIndex===5 && g.total>0 && g.unlocked===g.total)
    })
    function openFor(ids) { scopeIds=ids || [];backend.achievements.refreshCatalog();show();raise();requestActivate();Qt.callLater(function() { if(!detail.gameId && window.visibleGames.length) window.selectGame(Math.max(0,window.visibleGames.findIndex(function(g) { return g.has_schema }))) }) }
    function selectGame(index) { if(index>=0 && index<visibleGames.length) { games.currentIndex=index;chartGame=visibleGames[index].id;detail.loadFor(visibleGames[index].id) } }
    function choose(id,value) { var next=Object.assign({},selected);next[id]=value;selected=next }
    function selectVisible() { var next=Object.assign({},selected);visibleGames.forEach(function(g) { next[g.id]=true });selected=next }
    function start(force) {
        var ids=visibleGames.filter(function(g) { return selected[g.id] }).map(function(g) { return g.id })
        if(!ids.length) ids=visibleGames.map(function(g) { return g.id })
        if(ids.length) backend.achievements.batch(ids,backend.achievements.providers[provider.currentIndex].id,force)
    }
    function inside(item,parent) { while(item) { if(item===parent) return true;item=item.parent };return false }
    function controllerInput(command) {
        if(command==="back") { if(pages.currentIndex!==0) { pages.currentIndex=0;games.forceActiveFocus() } else if(inside(window.activeFocusItem,detail)) games.forceActiveFocus();else close();return true }
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
        return Form.handle([gamesTab,sourcesTab,recentTab,statsTab,search,kind,selectAll,tools,provider,refresh,full,stop,chartAll,chartCurrent,chartPeriod,chartLine,statsGame,statsPeriod,statsLine,save,closeButton],focus,command,null)
    }
    onVisibleGamesChanged: {
        var index=visibleGames.map(function(g) { return g.id }).indexOf(detail.gameId)
        games.currentIndex=index
        if(index<0 && detail.gameId) { detail.gameId="";chartGame="" }
    }
    ColumnLayout {
        anchors.fill: parent;anchors.margins: 22;spacing: 10
        RowLayout {
            Layout.fillWidth: true;spacing: 16
            ColumnLayout {
                spacing: 4
                Label { text: "成就管理";font.pixelSize: 26;font.bold: true }
                Label { text: "每一次探索，都留下记录";color: Theme.secondary;font.pixelSize: 12 }
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
            TabButton { id: statsTab;text: "统计总览" }
        }
        RowLayout {
            visible: pages.currentIndex===0;Layout.fillWidth: true
            AppTextField { id: search;objectName: "achievementsLibrarySearch";Layout.fillWidth: true;placeholderText: "搜索游戏" }
            AppComboBox { id: kind;objectName: "achievementsLibraryFilter";model: ["全部游戏","本地游戏","Steam 游戏","尚未匹配","记录缺失","已完成"];Layout.preferredWidth: 140 }
            AppButton { id: selectAll;text: "全选当前结果";onClicked: window.selectVisible() }
            AppButton { id: tools;objectName: "achievementBatchToggle";text: "批量与匹配";checkable: true }
        }
        RowLayout {
            visible: pages.currentIndex===0 && tools.checked;Layout.fillWidth: true
            AppComboBox { id: provider;objectName: "achievementsBatchProvider";Layout.fillWidth: true;model: backend.achievements.providers;textRole: "name" }
            AppButton { id: refresh;objectName: "achievementsBatchStart";text: "补全缺失并检测记录";highlighted: true;enabled: !backend.achievements.batchState.running;onClicked: window.start(false) }
            AppButton { id: full;text: "重新匹配所选";enabled: !backend.achievements.batchState.running;onClicked: window.start(true) }
            AppButton { id: stop;text: "停止";enabled: backend.achievements.batchState.running;onClicked: backend.achievements.cancelBatch() }
        }
        ProgressBar { Layout.fillWidth: true;visible: backend.achievements.batchState.running;from: 0;to: Math.max(1,backend.achievements.batchState.total);value: backend.achievements.batchState.done }
        Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: backend.achievements.batchState.message;visible: backend.achievements.batchState.running || tools.checked;color: Theme.secondary;font.pixelSize: 12 }
        RowLayout {
            visible: pages.currentIndex===0;Layout.fillWidth: true;Layout.fillHeight: true;Layout.minimumHeight: 200;spacing: 18
            ListView {
                id: games;objectName: "achievementsGameList";Layout.preferredWidth: window.width<1100 ? 255 : 340;Layout.fillHeight: true
                model: window.visibleGames;clip: true;spacing: 4;currentIndex: -1;reuseItems: true;boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData
                    required property int index
                    width: games.width;height: 112;radius: Theme.radius
                    color: games.currentIndex===index ? Theme.selection : Theme.surface;border.color: games.activeFocus && games.currentIndex===index ? Theme.accent : Theme.outline
                    Behavior on color { ColorAnimation { duration: Theme.motion ? 120 : 0 } }
                    TapHandler { onTapped: window.selectGame(index) }
                    CheckBox { id: checked;x: 0;y: 35;width: 32;checked: !!window.selected[modelData.id];onToggled: window.choose(modelData.id,checked) }
                    Rectangle {
                        x: 35;y: 10;width: 57;height: 82;radius: 4;color: Theme.sidebar;clip: true
                        Image { anchors.fill: parent;source: modelData.coverUrl || "";asynchronous: true;fillMode: Image.PreserveAspectCrop;sourceSize.width: 144 }
                        Label { anchors.centerIn: parent;visible: !modelData.coverUrl;text: "◇";font.pixelSize: 24;color: Theme.secondary }
                    }
                    Column {
                        x: 104;y: 12;width: parent.width-117;spacing: 7
                        Label { width: parent.width;text: modelData.name;elide: Text.ElideRight;font.bold: true }
                        Row { spacing: 7;Label { text: modelData.unlocked+" / "+modelData.total;color: Theme.accent;font.pixelSize: 12;font.bold: true } Label { text: modelData.total ? Math.round(modelData.unlocked/modelData.total*100)+"%" : "待匹配";color: Theme.secondary;font.pixelSize: 12 } }
                        ProgressBar { width: parent.width;from: 0;to: Math.max(1,modelData.total);value: modelData.unlocked;height: 5 }
                        Label { width: parent.width;text: modelData.status;elide: Text.ElideRight;color: Theme.secondary;font.pixelSize: 11 }
                        Label { width: parent.width;text: modelData.error || (modelData.platform==="steam" ? "Steam · " : "本地 · ")+"图标 "+modelData.icons_cached+"/"+modelData.icons_total;elide: Text.ElideRight;color: Theme.secondary;font.pixelSize: 11;ToolTip.text: modelData.error || text;ToolTip.visible: rowHover.hovered;HoverHandler { id: rowHover } }
                    }
                }
            }
            Rectangle { Layout.preferredWidth: 1;Layout.fillHeight: true;color: Theme.outline }
            Item {
                Layout.fillWidth: true;Layout.fillHeight: true
                AchievementsPane { id: detail;objectName: "achievementsLibraryDetail";anchors.fill: parent;visible: !!gameId;compact: true }
                Label { visible: !detail.gameId;anchors.centerIn: parent;width: parent.width-30;text: "从左侧选择游戏，查看成就、数据源与记录检测详情。\n批量补全会复用已有列表，下载缺失图标；Steam 游戏只统计，不重复弹窗。";wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter;color: Theme.secondary }
            }
        }
        ColumnLayout {
            visible: pages.currentIndex===0 && window.height>=820;Layout.fillWidth: true;Layout.preferredHeight: 210;Layout.minimumHeight: 210;Layout.maximumHeight: 210;spacing: 8
            RowLayout {
                Layout.fillWidth: true
                AppButton { id: chartAll;text: "全部游戏";flat: true;highlighted: !window.chartGame;onClicked: window.chartGame="" }
                AppButton { id: chartCurrent;text: "当前游戏";flat: true;highlighted: !!window.chartGame;enabled: !!detail.gameId;onClicked: window.chartGame=detail.gameId }
                Item { Layout.fillWidth: true }
                AppComboBox { id: chartPeriod;model: ["7 天","30 天","90 天","1 年","全部时间"];property var periods: [7,30,90,365,0];Layout.preferredWidth: 116;currentIndex: periods.indexOf(window.chartDays);onActivated: window.chartDays=periods[currentIndex] }
                AppButton { id: chartLine;text: window.cumulative ? "累计" : "期间";flat: true;onClicked: window.cumulative=!window.cumulative }
            }
            AchievementCharts { Layout.fillWidth: true;Layout.fillHeight: true;statistics: window.chartStatistics;perGame: !!window.chartGame;compact: true;cumulative: window.cumulative }
        }
        ColumnLayout {
            visible: pages.currentIndex===3;Layout.fillWidth: true;Layout.fillHeight: true;spacing: 12
            RowLayout {
                Layout.fillWidth: true
                AppComboBox {
                    id: statsGame;objectName: "achievementStatisticsGame";Layout.fillWidth: true;textRole: "name"
                    model: [{id:"",name:"全部游戏"}].concat(window.catalog.filter(function(g) { return g.total>0 }))
                    currentIndex: Math.max(0,model.findIndex(function(g) { return g.id===window.chartGame }))
                    onActivated: window.chartGame=model[currentIndex].id
                }
                AppComboBox { id: statsPeriod;objectName: "achievementStatisticsPeriod";model: ["7 天","30 天","90 天","1 年","全部时间"];property var periods: [7,30,90,365,0];Layout.preferredWidth: 125;currentIndex: periods.indexOf(window.chartDays);onActivated: window.chartDays=periods[currentIndex] }
                AppButton { id: statsLine;text: window.cumulative ? "累计曲线" : "解锁曲线";onClicked: window.cumulative=!window.cumulative }
            }
            RowLayout {
                Layout.fillWidth: true;spacing: 30
                Label { text: window.chartStatistics.unlocked+" 已解锁";font.pixelSize: 24;font.bold: true;color: Theme.accent }
                Label { text: window.chartStatistics.total+" 总成就";color: Theme.secondary }
                Label { text: window.chartStatistics.completed_games+" 款全成就";color: Theme.secondary }
                Item { Layout.fillWidth: true }
            }
            AchievementCharts { objectName: "achievementStatisticsCharts";Layout.fillWidth: true;Layout.preferredHeight: Math.max(230,window.height*.33);statistics: window.chartStatistics;perGame: !!window.chartGame;cumulative: window.cumulative }
            Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "时间未知的历史解锁计入完成度，不计入日期曲线。稀有度使用数据源的全球解锁率，没有来源的数据归为未知。";color: Theme.secondary;font.pixelSize: 12 }
            ListView {
                objectName: "achievementStatisticsGames";Layout.fillWidth: true;Layout.fillHeight: true;clip: true;spacing: 6;model: window.catalog.filter(function(g) { return g.total>0 && (!window.chartGame || g.id===window.chartGame) });ScrollBar.vertical: ScrollBar {}
                delegate: Rectangle {
                    required property var modelData;width: ListView.view.width;height: 62;radius: Theme.controlRadius;color: Theme.surface
                    TapHandler { onTapped: { window.chartGame=modelData.id;var index=window.visibleGames.findIndex(function(g) { return g.id===modelData.id });if(index>=0) window.selectGame(index);pages.currentIndex=0 } }
                    RowLayout { anchors.fill: parent;anchors.margins: 12;spacing: 16
                        Label { text: modelData.name;Layout.fillWidth: true;elide: Text.ElideRight }
                        ProgressBar { Layout.preferredWidth: 220;from: 0;to: Math.max(1,modelData.total);value: modelData.unlocked }
                        Label { text: modelData.unlocked+" / "+modelData.total;color: Theme.accent;Layout.preferredWidth: 90 }
                    }
                }
            }
        }
        ScrollView {
            id: sourceView;visible: pages.currentIndex===1;Layout.fillWidth: true;Layout.fillHeight: true;clip: true;contentWidth: availableWidth
            ColumnLayout {
                width: sourceView.availableWidth;spacing: 18
                Label { text: "成就定义来源";font.pixelSize: 20;font.bold: true }
                Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "定义提供名称、说明与每项独立图标；解锁进度来自本机记录。自动模式先读取 Steam，失败时使用本地定义，再尝试 SteamHunters、Steam Community 和 Completionist.me。";color: Theme.secondary }
                Repeater {
                    model: [{name:"Steam",description:"按明确 App ID 获取公开成就定义和每项独立图标，不需要登录好友账号。"},{name:"SteamHunters",description:"按相同 Steam App ID 请求备用定义；无法访问时保留缓存并报告失败。"},{name:"Steam Community",description:"读取新版公开成就页面中的内部 ID、名称、说明和独立图标，不按列表位置猜测对应关系。"},{name:"Completionist.me",description:"额外公开资料源。按唯一标题或同一图标关联已有定义；没有内部 ID 时保留为标题定义，不能强行对应 API 记录。网络限制会显示为失败。"},{name:"本地定义 / Steam 缓存",description:"导入 JSON 定义，或读取 Steam appcache/stats 下的定义缓存。批量补全复用已有数据，图标下载可续补。"},{name:"DeepSeek 辅助匹配",description:"使用现有 API Key 辅助识别游戏名称，再搜索并确认对应版本。模型不生成解锁记录或虚构图标。"}]
                    ColumnLayout {
                        required property var modelData;Layout.fillWidth: true;spacing: 7
                        Label { text: modelData.name;font.bold: true }
                        Label { text: modelData.description;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary }
                        Rectangle { Layout.fillWidth: true;implicitHeight: 1;color: Theme.outline }
                    }
                }
                Label { text: "本机进度来源";font.pixelSize: 20;font.bold: true }
                Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: "Steam：定位账号对应的 UserGameStats BIN，配对 Schema 解析位掩码。多个账号不会自动合并；Steam 条目统计成就，不重复弹窗。\n\n本地：支持 Goldberg / GSE JSON、CODEX / RUNE 兼容 INI、TENOKE 的 ACHIEVEMENTS 节以及部分文本记录。Count=0 是有效的空成就容器，会等待首次解锁；UserStats 的普通数值不是解锁标记。\n\nSmartSteamEmu stats.bin：按独立的 24 字节条目格式读取，CRC32 必须与定义内部 ID 唯一对应，普通统计不能充当成就。\n\nGOG Galaxy 数据库、模拟器奖杯及游戏私有存档尚需各自适配。来源名称相同也可能存在版本差异；没有可读输出的游戏不能只凭列表判定解锁。\n\n在“匹配与记录设置 → 检测详情”查看检查目录和原因；记录首次出现时会自动发现。";color: Theme.secondary }
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
                    Image { source: modelData.iconUrl || "";Layout.preferredWidth: 48;Layout.preferredHeight: 48;asynchronous: true;fillMode: Image.PreserveAspectFit }
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
