import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ControllerForm.js" as Form
import "AchievementStyle.js" as Style

ScrollView {
    id: pane
    objectName: "achievementsPane"
    property string gameId: ""
    readonly property var info: { if(backend.achievements.state.ident===gameId) return backend.achievements.state;var revision=backend.achievements.summaryRevision;return Object.assign({ident:gameId,rows:[],sources:[],total:0,unlocked:0,busy:false,message:"切回本页后读取详细记录"},backend.achievements.summary(gameId)) }
    property bool loaded: false
    property bool dirty: false
    property bool compact: false
    readonly property var game: { var revision=backend.libraryRevision;return backend.libraryGame(gameId) }
    readonly property bool entryOpen: entryDialog.visible
    readonly property bool listFocused: list.activeFocus
    property var activeEntry: ({})
    readonly property var filteredRows: {
        if(pane.info.ident!==pane.gameId) return []
        var q=achievementSearch.text.trim().toLowerCase(),rows=(pane.info.rows || []).filter(function(r) { return (filter.currentIndex===0 || filter.currentIndex===1 && !r.unlocked || filter.currentIndex===2 && r.unlocked) && (!q || ((hiddenToggle.checked ? r.secret_name+" "+r.secret_description : r.name+" "+r.description).toLowerCase().indexOf(q)>=0)) })
        if(sort.currentIndex===1) rows.sort(function(a,b) { return b.unlocked_time-a.unlocked_time })
        if(sort.currentIndex===2) rows.sort(function(a,b) { return (Style.known(a) ? a.rarity : 101)-(Style.known(b) ? b.rarity : 101) })
        return rows
    }
    AchievementRecords { id: entryRecords;objectName: "achievementEntryRecords" }
    function syncEntries() {
        entryRecords.updateRecords(filteredRows)
        var index=entryRecords.findId(list.navigationId)
        if(index>=0 && list.currentIndex!==index) list.currentIndex=index
    }
    onFilteredRowsChanged: syncEntries()
    function showEntry(row) { list.navigationId=row.id;activeEntry=row;entryDialog.open() }
    function focusEntries() { if(list.count) { list.currentIndex=Math.max(0,list.currentIndex);Form.reveal(list,pane);list.positionViewAtIndex(list.currentIndex,ListView.Contain) } else Form.reveal(setup,pane) }
    readonly property bool steamGame: backend.libraryGame(gameId).platform==="steam"
    readonly property bool localGame: !backend.libraryGame(gameId).platform || ["local","steam"].indexOf(backend.libraryGame(gameId).platform)>=0
    property string achievementQuery: ""
    clip: true
    contentWidth: availableWidth
    ScrollBar.vertical: AchievementScrollBar { objectName: "achievementPaneScrollBar" }
    function loadFor(ident) { if(ident!==gameId) { list.navigationId="";list.currentIndex=-1 };gameId=ident;loaded=false;dirty=false;query.text=backend.libraryGame(ident).name || "";backend.achievements.openFor(ident);Qt.callLater(function() { if(pane.contentItem && pane.contentItem.contentY!==undefined) pane.contentItem.contentY=0 }) }
    function save() { dirty=false;backend.achievements.save(gameId,{enabled:enabledToggle.checked,source:source.text,provider:backend.achievements.providers[provider.currentIndex].id}) }
    function controllerInput(command) {
        if(entryDialog.visible) { if(command==="back" || command==="activate") entryDialog.close();else if(command==="up" || command==="down") { var flick=descriptionView.contentItem;flick.contentY=Math.max(0,Math.min(Math.max(0,flick.contentHeight-flick.height),flick.contentY+(command==="up" ? -60 : 60))) };return true }
        if(list.activeFocus) {
            if(command==="up" && list.currentIndex<=0) { Form.reveal(resetFilter.visible ? resetFilter : achievementSearch,pane);return true }
            if(command==="up" || command==="down") { list.currentIndex=Math.max(0,Math.min(list.count-1,list.currentIndex+(command==="up" ? -1 : 1)));if(list.count) list.navigationId=entryRecords.get(list.currentIndex).record.id;list.positionViewAtIndex(list.currentIndex,ListView.Contain);return true }
            if(command==="activate" && list.currentIndex>=0 && list.currentIndex<list.count) { showEntry(entryRecords.get(list.currentIndex).record);return true }
            return true
        }
        if(command==="down" && pane.Window.window.activeFocusItem===resetFilter && list.count) { list.currentIndex=0;Form.reveal(list,pane);return true }
        return Form.handle([enabledToggle,setup,query,searchButton,aiSearch,candidates,chooseCandidate,provider,appid,matchButton,source,sourceChoice,pickSource,rootButton,diagnostics,importSchema,refreshButton,exportSchema,achievementSearch,filter,sort,hiddenToggle,resetFilter,list],pane.Window.window.activeFocusItem,command,pane)
    }
    Connections {
        target: pane.Window.window
        function onActiveChanged() { if(pane.Window.window.active && pane.visible && pane.gameId && backend.achievements.state.ident!==pane.gameId) pane.loadFor(pane.gameId) }
    }
    Connections {
        target: backend.achievements
        function onChanged() {
            if(pane.info.ident!==pane.gameId || pane.info.busy) return
            if(!pane.loaded) { setup.checked=!pane.info.has_schema;pane.loaded=true }
            enabledToggle.checked=pane.info.enabled!==false
            if(!pane.dirty) { source.text=pane.info.source || "";appid.text=pane.info.appid || "";provider.currentIndex=Math.max(0,backend.achievements.providers.map(function(p) { return p.id }).indexOf(pane.info.provider || "auto")) }
        }
    }
    ColumnLayout {
    width: Math.max(0,pane.availableWidth-16)
    spacing: 10
    AchievementHero { Layout.fillWidth: true;game: pane.game;info: pane.info;compact: pane.compact }
    RowLayout {
        Layout.fillWidth: true
        AppButton { id: setup;objectName: "achievementSetup";visible: pane.localGame;text: checked ? "收起设置" : "匹配与记录";checkable: true;flat: true }
        Item { Layout.fillWidth: true }
        Switch { id: enabledToggle;objectName: "achievementEnabled";text: "监听";enabled: pane.localGame && backend.achievements.enabled;onToggled: backend.achievements.setSwitches(pane.gameId,{enabled:checked}) }
    }
    Label { visible: !backend.achievements.enabled;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;text: "成就总开关已关闭，可在成就管理页面重新开启。" }
    Label { visible: setup.checked;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;text: "同步游戏的本机成就记录";font.pixelSize: 12 }
    Label { objectName: "achievementRecordStatus";visible: setup.checked || !pane.info.has_record;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;text: pane.info.record_status || "尚未检测记录";font.pixelSize: 12 }
    Label { objectName: "achievementMonitorStatus";visible: setup.checked || String(pane.info.monitor_status || "").indexOf("重试")>=0;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;text: pane.info.monitor_status || "等待检测监听状态";font.pixelSize: 12 }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: query;objectName: "achievementSearch";Layout.fillWidth: true;placeholderText: "搜索游戏名称";onAccepted: backend.achievements.search(pane.gameId,text) }
        AppButton { id: searchButton;objectName: "achievementSearchButton";text: "搜索匹配";enabled: !pane.info.busy;onClicked: backend.achievements.search(pane.gameId,query.text) }
        AppButton { id: aiSearch;objectName: "achievementAiSearch";text: "DeepSeek 匹配";enabled: !pane.info.busy && backend.settings.has_ai_key;onClicked: backend.achievements.search(pane.gameId,query.text,true) }
    }
    RowLayout {
        visible: (pane.info.candidates || []).length>0 && pane.localGame && setup.checked;Layout.fillWidth: true
        AppComboBox { id: candidates;objectName: "achievementCandidates";Layout.fillWidth: true;model: pane.info.candidates || [];textRole: "name" }
        AppButton { id: chooseCandidate;text: "使用此版本";enabled: !pane.info.busy && candidates.currentIndex>=0;onClicked: backend.achievements.match(pane.gameId,pane.info.candidates[candidates.currentIndex].appid) }
    }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        Label { text: "定义来源" }
        AppComboBox { id: provider;objectName: "achievementProvider";Layout.fillWidth: true;model: backend.achievements.providers;textRole: "name";onActivated: pane.dirty=true }
    }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: appid;objectName: "achievementAppId";Layout.fillWidth: true;placeholderText: "Steam App ID（从游戏资料自动识别）" }
        AppButton { id: matchButton;objectName: "achievementMatch";text: "匹配成就";enabled: !pane.info.busy && appid.text.length>0;onClicked: backend.achievements.matchSource(pane.gameId,appid.text.trim(),backend.achievements.providers[provider.currentIndex].id) }
    }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: source;objectName: "achievementSource";Layout.fillWidth: true;placeholderText: "进度记录 JSON / INI / Steam BIN";selectByMouse: true;onTextEdited: pane.dirty=true }
        AppButton { id: pickSource;text: "选择记录";enabled: !pane.info.busy;onClicked: backend.achievements.pickSource(pane.gameId) }
    }
    AppComboBox {
        id: sourceChoice;objectName: "achievementSourceChoice";Layout.fillWidth: true;visible: setup.checked && (pane.info.sources || []).length>1
        model: pane.info.sources || [];displayText: currentIndex>=0 ? currentText : "选择本次账号的记录";currentIndex: -1
        onActivated: { source.text=currentText;pane.dirty=true }
    }
    RowLayout {
        visible: setup.checked && pane.localGame;Layout.fillWidth: true;spacing: 8
        AppButton { id: importSchema;visible: pane.localGame && setup.checked;text: "导入定义";enabled: !pane.info.busy;onClicked: backend.achievements.importSchema(pane.gameId) }
        AppButton { id: refreshButton;visible: pane.localGame && setup.checked;text: "重新检测";enabled: !pane.info.busy;onClicked: backend.achievements.openFor(pane.gameId) }
        AppButton { id: rootButton;visible: pane.localGame && setup.checked;text: "添加检测目录";enabled: !pane.info.busy;onClicked: backend.achievements.addRoot(pane.gameId) }
        AppButton { id: diagnostics;visible: pane.localGame && setup.checked;text: "检测详情";checkable: true }
        Item { Layout.fillWidth: true }
    }
    Label { visible: setup.checked && diagnostics.checked;Layout.fillWidth: true;wrapMode: Text.Wrap;font.pixelSize: 11;color: Theme.secondary;text: "定义来源："+(pane.info.schema_source || "尚未匹配")+(pane.info.record_note ? "\n"+pane.info.record_note : "")+"\n检查目录：\n"+(pane.info.checked || []).join("\n")+((pane.info.rejected || []).length ? "\n未识别的记录：\n"+pane.info.rejected.map(function(r) { return r.path+"："+r.reason }).join("\n") : "") }
    RowLayout {
        visible: setup.checked && pane.localGame;Layout.fillWidth: true
        AppButton { id: exportSchema;objectName: "achievementExportDefinitions";text: "导出成就定义包";enabled: !!pane.info.has_schema && !pane.info.busy;onClicked: backend.achievements.exportDefinitions(pane.gameId) }
        Label { text: "导出到本程序数据目录，不自动安装或改动游戏。";color: Theme.secondary;font.pixelSize: 11;wrapMode: Text.Wrap;Layout.fillWidth: true }
    }
    RowLayout {
        visible: !pane.compact || setup.checked || pane.info.busy || !pane.info.has_schema;Layout.fillWidth: true
        AppBusyIndicator { running: pane.info.busy;visible: running;implicitWidth: 20;implicitHeight: 20 }
        Label { objectName: "achievementStatus";Layout.fillWidth: true;wrapMode: Text.Wrap;text: pane.info.message || "";color: Theme.secondary;font.pixelSize: 12 }
    }
    Label { visible: (pane.info.icons_total || 0)>0 && (!pane.compact || setup.checked || pane.info.icons_failed>0);Layout.fillWidth: true;color: Theme.secondary;font.pixelSize: 11;text: "图标缓存 "+(pane.info.icons_done || 0)+" / "+(pane.info.icons_total || 0)+(pane.info.icons_failed ? "，失败 "+pane.info.icons_failed+" 项，下次匹配重试" : "") }
    GridLayout {
        Layout.fillWidth: true;columns: pane.availableWidth<500 ? 3 : 4;columnSpacing: 8;rowSpacing: 6
        AppTextField { id: achievementSearch;objectName: "achievementListSearch";Layout.columnSpan: pane.availableWidth<500 ? 3 : 1;Layout.fillWidth: true;placeholderText: "搜索成就名称、说明" }
        AppComboBox { id: filter;objectName: "achievementListFilter";model: ["全部","未解锁","已解锁"];Layout.preferredWidth: 100 }
        AppComboBox { id: sort;objectName: "achievementListSort";model: ["默认排序","最近解锁","稀有度"];Layout.preferredWidth: 116 }
        CheckBox { id: hiddenToggle;objectName: "achievementRevealHidden";text: "显示隐藏" }
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "成就列表";font.pixelSize: 13;font.weight: Font.DemiBold }
        Label { objectName: "achievementResultCount";text: list.count+" 项";font.pixelSize: 11;color: Theme.secondary }
        Item { Layout.fillWidth: true }
        AppButton { id: resetFilter;objectName: "achievementResetFilters";text: "重置筛选";flat: true;visible: !!achievementSearch.text || filter.currentIndex!==0 || sort.currentIndex!==0 || hiddenToggle.checked;onClicked: { achievementSearch.clear();filter.currentIndex=0;sort.currentIndex=0;hiddenToggle.checked=false } }
    }
    ListView {
        id: list;objectName: "achievementList";Layout.fillWidth: true;Layout.preferredHeight: Math.max(180,pane.availableHeight-list.y-12);clip: true;spacing: 4
        property string navigationId: ""
        Keys.onReturnPressed: if(currentIndex>=0 && currentIndex<count) pane.showEntry(entryRecords.get(currentIndex).record)
        Keys.onEnterPressed: if(currentIndex>=0 && currentIndex<count) pane.showEntry(entryRecords.get(currentIndex).record)
        Keys.onUpPressed: pane.controllerInput("up")
        Keys.onDownPressed: pane.controllerInput("down")
        model: entryRecords
        currentIndex: -1;reuseItems: true;boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: AchievementScrollBar { objectName: "achievementEntryScrollBar" }
        delegate: AchievementEntry {
            required property int index
            objectName: "achievementEntry";width: list.width;height: implicitHeight
            compact: pane.compact;revealHidden: hiddenToggle.checked;selected: list.activeFocus && list.currentIndex===index
            onClicked: { list.currentIndex=index;pane.showEntry(record) }
        }
        Label { anchors.centerIn: parent;width: parent.width-30;wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter;visible: !list.count;text: pane.info.has_schema ? "没有符合筛选条件的成就\n试试其他关键词，或重置筛选。" : "还没有成就列表\n展开匹配与记录设置，选择游戏版本后查看。";color: Theme.secondary }
    }
    }
    Dialog {
        id: entryDialog;objectName: "achievementEntryDialog";parent: Overlay.overlay
        function controllerInput(command) { return pane.controllerInput(command) }
        anchors.centerIn: parent;width: Math.min(540,parent ? parent.width-48 : 540)
        modal: true;focus: true;padding: 24;closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle { color: Theme.sidebar;radius: Theme.radius;border.color: Theme.outline }
        Overlay.modal: Rectangle { color: Theme.dark ? "#aa000000" : "#66000000" }
        onClosed: Qt.callLater(function() { list.forceActiveFocus();if(list.currentIndex>=0) list.positionViewAtIndex(list.currentIndex,ListView.Contain) })
        contentItem: ColumnLayout {
            spacing: 16
            RowLayout {
                Layout.fillWidth: true;spacing: 18
                Rectangle {
                    Layout.preferredWidth: 76;Layout.preferredHeight: 76;radius: 8;color: Theme.surface
                    Label { anchors.centerIn: parent;text: pane.activeEntry.hidden && !pane.activeEntry.unlocked && !hiddenToggle.checked ? "?" : pane.activeEntry.unlocked ? "✓" : "◇";font.pixelSize: 32;color: Theme.accent;visible: detailIcon.status!==Image.Ready || !detailIcon.visible }
                    Image { id: detailIcon;anchors.fill: parent;anchors.margins: 4;source: pane.activeEntry.iconUrl || "";sourceSize.width: 160;asynchronous: true;fillMode: Image.PreserveAspectFit;visible: !pane.activeEntry.hidden || !!pane.activeEntry.unlocked || hiddenToggle.checked }
                }
                ColumnLayout {
                    Layout.fillWidth: true;spacing: 8
                    Label { objectName: "achievementEntryTitle";text: Style.title(pane.activeEntry,hiddenToggle.checked) || "成就详情";textFormat: Text.PlainText;font.pixelSize: 20;font.weight: Font.DemiBold;Layout.fillWidth: true;wrapMode: Text.Wrap;maximumLineCount: 3;elide: Text.ElideRight }
                    Label { text: pane.activeEntry.unlocked ? "已解锁 · "+(pane.activeEntry.unlocked_at || "时间未知") : "尚未解锁";color: pane.activeEntry.unlocked ? Theme.accent : Theme.secondary;font.pixelSize: 12 }
                }
            }
            Rectangle { Layout.fillWidth: true;implicitHeight: 1;color: Theme.outline }
            ScrollView {
                id: descriptionView;objectName: "achievementDescriptionScroll";Layout.fillWidth: true;Layout.preferredHeight: Math.min(200,entryDescription.implicitHeight);clip: true;contentWidth: availableWidth
                ScrollBar.vertical: AchievementScrollBar { objectName: "achievementDescriptionScrollBar" }
                Label { id: entryDescription;objectName: "achievementEntryDescription";text: Style.description(pane.activeEntry,hiddenToggle.checked) || "暂无说明";textFormat: Text.PlainText;width: descriptionView.availableWidth;wrapMode: Text.Wrap;font.pixelSize: 14;lineHeight: 1.4 }
            }
            ProgressBar { visible: pane.activeEntry.max>0 && !pane.activeEntry.unlocked;Layout.fillWidth: true;from: 0;to: Math.max(1,pane.activeEntry.max || 0);value: pane.activeEntry.progress || 0 }
            Label { visible: pane.activeEntry.max>0 && !pane.activeEntry.unlocked;text: "当前进度 "+(pane.activeEntry.progress || 0)+" / "+(pane.activeEntry.max || 0);color: Theme.secondary }
            Label { text: Style.rarity(pane.activeEntry)+(Style.known(pane.activeEntry) ? " · 全球解锁率 "+Number(pane.activeEntry.rarity).toFixed(1)+"%" : "");color: Style.color(pane.activeEntry,Theme.secondary,Theme.dark);font.pixelSize: 12 }
            AppButton { objectName: "achievementEntryClose";text: "返回成就列表";Layout.alignment: Qt.AlignRight;onClicked: entryDialog.close() }
        }
    }
}
