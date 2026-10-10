import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material

ApplicationWindow {
    id: win
    visible: true
    width: 1440; height: 940
    minimumWidth: 900; minimumHeight: 650
    title: "GameCloudSave · V2.3.3"
    color: Theme.background
    Material.theme: Theme.dark ? Material.Dark : Material.Light
    Material.accent: Theme.accent
    Material.background: Theme.surface
    Overlay.modal: Rectangle { color: "#bb000000" }
    font.family: "Microsoft YaHei UI"
    property string activeId: ""
    property string activeName: ""
    property int coverSize: backend.settings.cover_size
    property int columnCount: backend.settings.columns
    property int gridGap: backend.settings.gap
    property bool installedOnly: backend.settings.installed_only
    property string searchQuery: ""
    property string platformFilter: "all"
    property string importSourceFilter: "all"
    property string libraryMode: "home"
    property string groupFilter: ""
    property string seriesFilter: ""
    property string librarySort: "name"
    property bool libraryReady: false
    property int filterFocusIndex: 0
    property int headerFocusIndex: 0
    readonly property var filterControls: [installedControl,platformControl,sourceControl,seriesControl,sortControl]
    readonly property var headerControls: [backButton,search,watchControl]
    property var navigationHistory: []
    function goBack() {
        var previous=navigationHistory.length ? navigationHistory[navigationHistory.length-1] : {mode:"home",category:"",series:"",search:"",y:0,gridY:0,gridIndex:0}
        navigationHistory=navigationHistory.slice(0,-1)
        searchDelay.stop();search.text=previous.search;searchQuery=previous.search;searchDelay.stop()
        libraryMode=previous.mode;librarySort=previous.sort || (previous.mode==="recent" ? "recent" : "name");groupFilter=previous.category;seriesFilter=previous.series
        Qt.callLater(function() { if(win.homeVisible) home.restorePosition(previous.y);else { grid.currentIndex=Math.min(grid.count-1,previous.gridIndex || 0);grid.contentY=previous.gridY || 0;grid.forceActiveFocus() } })
    }
    function libraryFocus() {
        var item=activeFocusItem
        while(item) { if(item===home || item===grid) return true;item=item.parent }
        return !activeFocusItem || activeFocusItem===contentItem
    }
    function focusContent() { if(homeVisible) home.forceActiveFocus();else grid.forceActiveFocus() }
    function focusControls(items,index) {
        var available=items.filter(function(item) { return item.visible && item.enabled })
        if(available.length) { available[Math.max(0,Math.min(available.length-1,index))].forceActiveFocus();backend.navigationMoved() }
    }
    function controllerInput(command) {
        if(!win.active || backend.popupActive()) return false
        if(command==="back") { if(libraryMode!=="home" || searchQuery || navigationHistory.length) goBack();else home.forceActiveFocus();return true }
        var sidebar=[navHome,navAll,navRecent,navFavorites,navSeries]
        var filters=filterControls.filter(function(control) { return control.visible && control.enabled })
        var headers=headerControls.filter(function(control) { return control.visible && control.enabled })
        var item=activeFocusItem,side=-1,filter=-1,header=-1
        while(item) { if(side<0) side=sidebar.indexOf(item);if(filter<0) filter=filters.indexOf(item);if(header<0) header=headers.indexOf(item);item=item.parent }
        if(side>=0) {
            if(command==="right") { focusContent();return true }
            if(command==="up" || command==="down") { focusControls(sidebar,side+(command==="up" ? -1 : 1));return true }
            if(command==="activate") { sidebar[side].clicked();return true }
            return true
        }
        if(filter>=0 || header>=0) {
            var available=filter>=0 ? filters : headers,position=filter>=0 ? filter : header
            if(filter>=0) filterFocusIndex=filter;else headerFocusIndex=header
            if(command==="up") { if(filter>=0) focusControls(headers,headerFocusIndex);return true }
            if(command==="down") { if(header>=0) focusControls(filters,filterFocusIndex);else focusContent();return true }
            if(command==="left" || command==="previous" || command==="right" || command==="next") {
                var step=(command==="left" || command==="previous") ? -1 : 1
                if(position===0 && step<0) focusControls(sidebar,0);else focusControls(available,position+step)
                return true
            }
            if(command==="activate") {
                if(header>=0 && headers[header]===search) { searchKeyboard.start(search.text);return true }
                if(header>=0 && headers[header]===watchControl) { watchControl.toggle();watchControl.toggled();return true }
                if(filter>=0 && filters[filter]===installedControl) { installedControl.toggle();installedControl.toggled();return true }
                if(header>=0 && headers[header]===backButton) goBack()
            }
            return true
        }
        if(command==="next" || command==="previous") return false
        if(!libraryFocus()) {
            if(["up","down","left","right"].indexOf(command)<0) return true
            focusContent()
        }
        if(command==="left" && (homeVisible ? !home.currentShelf() || home.currentShelf().selectionIndex<=0 : grid.currentIndex<=0 || grid.currentIndex%grid.effectiveColumns===0)) { focusControls(sidebar,Math.max(0,["home","all","recent","favorites","series"].indexOf(libraryMode)));return true }
        if(command==="up" && (homeVisible ? home.focusedSection===0 : grid.currentIndex<grid.effectiveColumns)) { focusControls(filters,filterFocusIndex);return true }
        if(["up","down","left","right"].indexOf(command)>=0) {
            if(homeVisible) home.navigateFocus(command)
            else if(grid.count) {
                var index=Math.max(0,grid.currentIndex),step=command==="left" ? -1 : command==="right" ? 1 : command==="up" ? -grid.effectiveColumns : grid.effectiveColumns
                grid.navigateFocus(Math.max(0,Math.min(grid.count-1,index+step)))
            }
            return true
        }
        if(homeVisible && command==="activate") { home.activateSelected();return true }
        var game=homeVisible ? home.selectedGame() : grid.count ? libraryModel.get(Math.max(0,grid.currentIndex)).record : null
        if(!game || !game.id) return false
        if(command==="activate") controllerGameMenu.showGame(game)
        else if(command==="favorite") backend.toggleFavorite(game.id)
        else if(command==="launch") backend.launch(game.id)
        else if(command==="history") controllerGameMenu.showGame(game)
        else return false
        return true
    }
    ListModel { id: libraryModel; dynamicRoles: true }
    Timer { id: searchDelay; interval: 120; onTriggered: win.searchQuery=search.text.trim().toLowerCase() }
    property var seriesNames: ((backend.librarySections.find(function(section) { return section.id==="series" }) || {}).items || []).map(function(item) { return item.name })
    property var searchTokens: searchQuery.split(/[,，\s]+/).map(function(token) { return token.replace(/^#/,'') }).filter(Boolean)
    property bool homeVisible: libraryMode==="home" && searchTokens.length===0 && shownGames.length>0
    property var homeRows: { var revision=backend.games;return backend.homeSections(installedOnly,platformFilter,importSourceFilter) }
    property var shownGames: backend.games.filter(function(g) { return (!installedOnly || g.installed) && (platformFilter==="all" || (g.platform || "local")===platformFilter || platformFilter==="local" && g.platform==="other") && (importSourceFilter==="all" || g.import_source===importSourceFilter) && searchTokens.every(function(token) { return (g.searchText || g.name.toLowerCase()).indexOf(token)>=0 }) && (libraryMode!=="favorites" || g.favorite) && (libraryMode!=="recent" || g.last_played) && (libraryMode!=="group" || (g.groups || []).indexOf(groupFilter)>=0) && (libraryMode!=="category" || g.category===groupFilter) && (libraryMode!=="series" || seriesNames.indexOf(g.series)>=0 && (!seriesFilter || g.series===seriesFilter)) }).sort(function(a,b) { if(librarySort==="release_asc" || librarySort==="release_desc") {
        var ad=a.release_date || "",bd=b.release_date || ""
        if(!ad || !bd) return ad ? -1 : bd ? 1 : a.name.localeCompare(b.name)
        return (librarySort==="release_asc" ? ad.localeCompare(bd) : bd.localeCompare(ad)) || a.name.localeCompare(b.name)
    }
    return librarySort==="recent" ? (b.last_played || "").localeCompare(a.last_played || "") || a.name.localeCompare(b.name) : librarySort==="added" ? (b.added_at || "").localeCompare(a.added_at || "") || a.name.localeCompare(b.name) : a.name.localeCompare(b.name) })
    function navigate(mode,value) {
        navigationHistory=navigationHistory.slice(-29).concat([{mode:libraryMode,category:groupFilter,series:seriesFilter,search:searchQuery,y:home.contentPosition(),gridY:grid.contentY,gridIndex:grid.currentIndex,sort:librarySort}])
        search.text="";searchQuery="";groupFilter="";seriesFilter=""
        if(mode==="tag") { libraryMode="all";search.text="#"+value;searchQuery=search.text.toLowerCase() }
        else { libraryMode=mode;librarySort=mode==="recent" ? "recent" : "name";if(mode==="category") groupFilter=value;if(mode==="series") seriesFilter=value }
        Qt.callLater(function() { if(win.homeVisible) home.forceActiveFocus();else grid.forceActiveFocus() })
    }
    onShownGamesChanged: if(libraryReady) syncLibrary()
    function syncLibrary() {
        for(var i=0;i<shownGames.length;i++) {
            var position=-1
            for(var j=i;j<libraryModel.count;j++) if(libraryModel.get(j).record.id===shownGames[i].id) { position=j;break }
            if(position<0) libraryModel.insert(i,{record:shownGames[i]})
            else { if(position!==i) libraryModel.move(position,i,1);libraryModel.set(i,{record:shownGames[i]}) }
        }
        while(libraryModel.count>shownGames.length) libraryModel.remove(libraryModel.count-1)
    }
    onClosing: function(close) { if(backend.closeToTray()) { close.accepted=false; cloudWindow.hide(); matchWindow.hide(); importWindow.hide(); batchWindow.hide();setupWizard.hide();libraryManager.hide();personalization.hide();enrichmentWindow.hide();hide() } else Qt.quit() }
    function selectGame(g) { activeId = g.id; activeName = g.name }
    function editMetadata() { gameDialog.openFor(activeId,2) }
    function openGame(g) {
        if(backend.controllerMode) { controllerGameMenu.showGame(g);return }
        selectGame(g);gameDialog.openFor(g.id,0)
    }
    function openEnrichment(ids,options,autoStart) { enrichmentWindow.openFor(ids || [],options || {},!!autoStart) }
    function openSettings() { openSettingsPage(0) }
    function openSettingsPage(page) {
        guideDialog.close()
        var s = backend.settings
        playnitePath.text = s.playnite; libraryPath.text = s.library
        snapshotPath.text = s.snapshots
        watchSwitch.checked=s.watch
        autoUpload.checked=s.watch_upload
        traySwitch.checked=s.close_to_tray; watchInterval.value=s.watch_interval
        settingsTabs.currentIndex=typeof page==="number" ? page : 0
        settingsDialog.open()
    }
    function openCloud() { guideDialog.close(); cloudWindow.openBrowser() }
    function openMatch(ident) { guideDialog.close(); matchWindow.openMatcher(ident || "") }
    function openImport() { guideDialog.close(); importWindow.openImporter() }
    function openBatch() { guideDialog.close();batchWindow.openBatch() }
    function openSetup() { guideDialog.close();setupWizard.openWizard() }
    function saveLayout() { backend.saveLayout({cover_size:coverSize, columns:columnCount, gap:gridGap, installed_only:installedOnly}) }
    ControllerKeyboard {
        id: searchKeyboard; objectName: "controllerKeyboard"
        width: Math.min(820,win.width-48); anchors.centerIn: parent
        quickTerms: backend.searchTerms
        onSubmitted: function(value) { search.text=value;searchDelay.stop();win.searchQuery=value.trim().toLowerCase();Qt.callLater(win.focusContent) }
        onCancelled: search.forceActiveFocus()
    }
    ControllerGameMenu { id: controllerGameMenu; anchors.centerIn: parent; width: Math.min(600,win.width-48) }
    EnrichmentWindow { id: enrichmentWindow }
    Connections { target: backend; function onEnrichmentRequested(ids,options) { win.openEnrichment(ids,options,true) } }
    CloudWindow { id: cloudWindow; objectName: "cloudWindow" }
    ImportWindow { id: importWindow; objectName: "importWindow" }
    BatchWindow { id: batchWindow; objectName: "batchWindow" }
    SetupWizard { id: setupWizard; objectName: "setupWizard" }
    LibraryManager { id: libraryManager; objectName: "libraryManager" }
    PersonalizationWindow { id: personalization; objectName: "personalization" }
    MatchWindow { id: matchWindow; objectName: "matchWindow"; onBatchRequested: win.openBatch() }
    Component.onCompleted: { libraryReady=true;syncLibrary();if(!backend.settings.setup_completed) setupWizard.openWizard();else if(!backend.settings.guide_dismissed) guideDialog.open() }


    Rectangle {
        width: 200; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: Theme.sidebar
        Row {
            x: 16; y: 24; spacing: 10
            Image { source: "icons/app.svg"; width: 28; height: 28; sourceSize: Qt.size(84,84) }
            Label { text: "GameCloudSave"; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 12; font.bold: true }
        }
        ScrollView { anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 84; bottom: parent.bottom; bottomMargin: 80 }
            clip: true
            Column { x: 8; spacing: 4
                NavigationButton { id: navHome; objectName: "navHome"; width: 184; iconName: "grid"; text: "游戏库主页"; selected: libraryMode==="home"; onClicked: win.navigate("home","") }
                NavigationButton { id: navAll; objectName: "navAll"; width: 184; iconName: "grid"; text: "全部游戏"; selected: libraryMode==="all"; onClicked: win.navigate("all","") }
                NavigationButton { id: navRecent; objectName: "navRecent"; width: 184; iconName: "play"; text: "最近游玩"; selected: libraryMode==="recent"; onClicked: win.navigate("recent","") }
                NavigationButton { id: navFavorites; objectName: "navFavorites"; width: 184; iconName: "star"; text: "收藏"; selected: libraryMode==="favorites"; onClicked: win.navigate("favorites","") }
                NavigationButton { id: navSeries; objectName: "navSeries"; width: 184; iconName: "folder"; text: "系列"; selected: libraryMode==="series"; onClicked: win.navigate("series","") }
                Rectangle { width: 184; height: 1; color: Theme.border }
                NavigationButton { objectName: "enrichmentNav"; width: 184; iconName: "spark"; text: "资料补全"; onClicked: win.openEnrichment([],{},false) }
                NavigationButton { width: 184; iconName: "cloud"; text: "云端存储"; onClicked: win.openCloud() }
                NavigationButton { width: 184; iconName: "folder"; text: "查找存档"; onClicked: win.openMatch("") }
                NavigationButton { width: 184; iconName: "grid"; text: "批量确认"; onClicked: win.openBatch() }
                NavigationButton { width: 184; iconName: "help"; text: "使用指南"; onClicked: guideDialog.open() }
                NavigationButton { width: 184; iconName: "settings"; text: "管理分类与系列"; onClicked: libraryManager.openManager() }
            }
        }
        NavigationButton { x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; iconName: "settings"; text: "设置"; onClicked: win.openSettings() }
    }

    ColumnLayout {
        anchors { left: parent.left; leftMargin: 232; right: parent.right; rightMargin: 32; top: parent.top; topMargin: 28; bottom: parent.bottom; bottomMargin: 18 }
        spacing: 18
        RowLayout {
            Layout.fillWidth: true
            AppButton { id: backButton; objectName: "libraryBack"; text: "返回"; visible: libraryMode!=="home" || searchTokens.length>0; onClicked: win.goBack() }
            ColumnLayout {
                spacing: 4
                Label { text: searchTokens.length ? "搜索结果" : libraryMode==="home" ? "游戏库" : libraryMode==="favorites" ? "我的收藏" : libraryMode==="recent" ? "最近游玩" : libraryMode==="group" || libraryMode==="category" ? groupFilter : libraryMode==="series" ? "系列游戏" : "全部游戏"; font.pixelSize: 30; font.bold: true; color: Theme.text }
                Label { text: shownGames.length+" 款游戏"; color: Theme.secondary; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            AppTextField { id: search; objectName: "search"; clip: true; Keys.onEscapePressed: text=""; onTextChanged: searchDelay.restart(); placeholderText: "搜索名称、标签、系列…"; Layout.preferredWidth: win.width<1100 ? 130 : 220; selectByMouse: true }
            Switch {
                id: watchControl; objectName: "watchControl"; text: "自动监听"; checked: backend.settings.watch; enabled: !backend.busy
                onToggled: backend.saveSettings({watch:checked})
                Rectangle { objectName: "watchFocusRing"; anchors.fill: parent; anchors.margins: -3; z: 10; color: "transparent"; radius: 6; border.width: 3; border.color: Theme.text; visible: watchControl.activeFocus }
            }
            AppButton { id: importControl; text: "导入游戏"; onClicked: win.openImport() }
        }
        GridLayout {
            Layout.fillWidth: true; columns: win.width<1700 ? 1 : 2
            rowSpacing: 2; columnSpacing: 16
            RowLayout {
                Layout.fillWidth: true
                CheckBox { id: installedControl; objectName: "installedFilter"; text: "仅已安装"; checked: installedOnly; onToggled: { installedOnly=checked; saveLayout() } }
                AppComboBox { id: platformControl; objectName: "platformFilter"; model: ["全部平台","Steam","Epic","Ubisoft","本地 / 其他"]; Layout.preferredWidth: 140; onActivated: platformFilter=["all","steam","epic","ubisoft","local"][currentIndex] }
                AppComboBox { id: sourceControl; model: ["全部来源","Playnite","游戏平台","本地扫描"]; Layout.preferredWidth: 130; onActivated: importSourceFilter=["all","playnite","platform","folder"][currentIndex] }
                AppComboBox { id: seriesControl; visible: libraryMode==="series"; model: ["全部系列"].concat(seriesNames); Layout.preferredWidth: 140; currentIndex: Math.max(0,model.indexOf(seriesFilter)); onActivated: seriesFilter=currentIndex>0 ? currentText : "" }
                Item { Layout.fillWidth: true }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                AppComboBox { id: sortControl; objectName: "librarySort"; currentIndex: ["name","recent","added","release_asc","release_desc"].indexOf(librarySort); visible: !homeVisible; model: ["名称排序","最近游玩","最近添加","发行日期: 从早到晚","发行日期: 从晚到早"]; Layout.preferredWidth: Math.max(200,implicitWidth); onActivated: librarySort=["name","recent","added","release_asc","release_desc"][currentIndex] }
                AppButton { id: layoutControl; text: "布局"; onClicked: win.openSettingsPage(2) }
                AppButton { id: personalControl; text: "个性化"; onClicked: personalization.openPersonalization() }
                Item { Layout.fillWidth: win.width<1200 }
            }
        }
        LibraryHome {
            id: home; objectName: "libraryHome"; visible: homeVisible
            Layout.fillWidth: true; Layout.fillHeight: true; sections: homeRows
            onBrowseRequested: function(mode,value) { win.navigate(mode,value) }
            onDetailsRequested: function(game) { win.openGame(game) }
            onLaunchRequested: function(game) { backend.launch(game.id) }
            onCloudRequested: function(game) { selectGame(game);historyTabs.currentIndex=0;backend.history(activeId);historyDialog.open() }
        }
        GridView {
            id: grid
            objectName: "gameGrid"
            activeFocusOnTab: true
            function navigateFocus(index) {
                var previousIndex=currentIndex,previousY=contentY
                gridScroll.stop();currentIndex=index
                positionViewAtIndex(currentIndex,GridView.Contain)
                var destination=contentY
                forceActiveFocus();contentY=previousY
                gridScroll.to=destination;gridScroll.restart()
                if(previousIndex!==currentIndex) backend.navigationMoved()
            }
            NumberAnimation { id: gridScroll; target: grid; property: "contentY"; duration: Theme.motion ? 190 : 0; easing.type: Easing.OutCubic }
            Keys.onPressed: function(event) {
                var commands={};commands[Qt.Key_Left]="left";commands[Qt.Key_Right]="right";commands[Qt.Key_Up]="up";commands[Qt.Key_Down]="down";commands[Qt.Key_Return]="activate";commands[Qt.Key_Enter]="activate";commands[Qt.Key_Escape]="back"
                if(commands[event.key]) event.accepted=win.controllerInput(commands[event.key])
            }
            visible: !homeVisible
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            property int effectiveColumns: Math.max(1, Math.min(Math.floor(width / (196 + gridGap)), columnCount > 0 ? columnCount : Math.floor(width / (coverSize + gridGap))))
            cellWidth: columnCount>0 ? width / effectiveColumns : Math.min(width,coverSize+gridGap)
            property real cardWidth: cellWidth - gridGap
            cellHeight: cardWidth * 1.38 + 144 + gridGap
            model: libraryModel
            cacheBuffer: cellHeight*2
            reuseItems: true
            flickDeceleration: 2200
            maximumFlickVelocity: 3500
            ScrollBar.vertical: ScrollBar { }
            delegate: Item {
                required property var record
                required property int index
                property var modelData: record
                width: grid.cellWidth; height: grid.cellHeight
                GameCard {
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: grid.cardWidth; height: grid.cellHeight-gridGap
                    game: modelData; scrolling: grid.moving || gridScroll.running
                    selected: grid.activeFocus && index===grid.currentIndex
                    transferState: backend.transferStates[modelData.id] || "idle"
                    onLaunchRequested: backend.launch(modelData.id)
                    onSettingsRequested: win.openGame(modelData)
                    onCloudRequested: { selectGame(modelData); historyTabs.currentIndex=0; backend.history(activeId); historyDialog.open() }
                    onRemoveRequested: { selectGame(modelData); deleteDialog.open() }
                    onFavoriteRequested: backend.toggleFavorite(modelData.id)
                }
            }
            Column {
                visible: grid.count === 0; anchors.centerIn: parent; spacing: 15
                Label { text: backend.games.length ? "没有匹配的游戏" : "尚未导入游戏"; font.pixelSize: 25; font.bold: true; anchors.horizontalCenter: parent.horizontalCenter }
                Label { text: libraryMode==="recent" ? "启动游戏后会显示在这里。" : libraryMode==="favorites" ? "点击游戏封面上的星号收藏。" : libraryMode==="series" ? "在分类管理中设置或识别系列。" : "导入游戏后，选择需要备份的存档。"; color: Theme.secondary }
                AppButton { text: "设置本机路径"; anchors.horizontalCenter: parent.horizontalCenter; onClicked: win.openSettings() }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            BusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 }
            ProgressBar { visible: backend.matching; Layout.preferredWidth: 140; indeterminate: backend.matching && backend.matchProgress.done===0; from: 0; to: Math.max(1,backend.matchProgress.total); value: backend.matchProgress.done }
            Label { visible: backend.matching; text: backend.matchProgress.done+" / "+backend.matchProgress.total; font.pixelSize: 12; color: Theme.secondary }
            AppButton { visible: backend.matching; text: backend.matchProgress.cancelled ? "正在停止" : "停止查找"; enabled: !backend.matchProgress.cancelled; onClicked: backend.cancelMatching() }
            Rectangle { visible: !backend.busy; width: 6; height: 6; radius: 3; color: Theme.accent }
            Label { text: backend.status; color: Theme.secondary; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight; ToolTip.visible: statusHover.hovered; ToolTip.text: text; HoverHandler { id: statusHover } }
            Label { visible: backend.gamepadConnected; text: "A 查看  B 返回  X 收藏  Y 存档  Menu 启动"; color: Theme.secondary; font.pixelSize: 11 }
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
                Label { text: "管理 Windows 游戏存档。可从 Playnite、游戏平台或本地文件夹导入，存档路径按当前电脑设置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                Label { text: "1. 导入游戏"; font.bold: true }
                Label { text: backend.games.length ? "已导入 "+backend.games.length+" 款游戏。新增游戏后可再次导入。" : "在设置里选择 Playnite 程序和 library 目录，保存后导入。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                RowLayout {
                    AppButton { text: "设置 Playnite 路径"; onClicked: { guideDialog.close(); win.openSettings() } }
                    AppButton { text: "导入游戏"; enabled: !backend.busy; onClicked: { guideDialog.close(); win.openImport() } }
                }
                Label { text: "2. 确认存档目录"; font.bold: true }
                Label { text: "先选一款玩过的游戏查找。核对候选目录，也可手动选择。多份存档应选择包含全部槽位的目录。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "查找存档"; enabled: backend.games.length>0; onClicked: { guideDialog.close(); win.openMatch("") } }
                Label { text: "3. 选择备份方式"; font.bold: true }
                Label { text: "游戏卡片的云朵按钮打开备份记录，可仅备份到本地。需要上传时，先设置 DAV 连接并选择云端文件夹；所有游戏共用这个位置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "设置云端存储（可选）"; onClicked: { guideDialog.close(); win.openCloud() } }
                Label { text: "4. 恢复存档"; font.bold: true }
                Label { text: "关闭游戏后，在存档记录中选择版本恢复。恢复前先备份当前存档。“云端 / 其他设备”页可刷新、下载并恢复其他设备的版本。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
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
                Label { text: "保存后，打开“导入游戏”的 Playnite 页面读取游戏库。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===1; Layout.fillWidth: true; spacing: 10
                Label { text: "本地备份目录" }
                RowLayout { AppTextField { id: snapshotPath; Layout.fillWidth: true; selectByMouse: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(snapshotPath.text); if(p) snapshotPath.text=p } } }
                Switch { id: watchSwitch; text: "监听游戏启动与退出并备份" }
                CheckBox { id: traySwitch; text: "关闭主窗口时留在托盘"; checked: backend.settings.close_to_tray }
                RowLayout { Label { text: "监听间隔（秒）"; Layout.fillWidth: true } CompactSpinBox { id: watchInterval; from: 5; to: 60; stepSize: 5; value: backend.settings.watch_interval } }
                CheckBox { id: autoUpload; text: "自动备份后上传云端"; enabled: watchSwitch.checked }
                Label { text: "自动备份需要在游戏设置中配置启动 EXE 和存档目录。上传失败会保留本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "设置云端连接与备份文件夹"; Layout.fillWidth: true; onClicked: win.openCloud() }
                Label { text: backend.settings.cloud_folder ? "云端文件夹："+backend.settings.cloud_folder : "尚未设置云端，可先使用本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                Label { text: "传输超时、重试次数和按电脑分目录，可在云端窗口的传输选项中设置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===2; Layout.fillWidth: true; spacing: 12
                Label { text: "修改后立即预览，点击保存保留布局。"; color: Theme.secondary }
                RowLayout { Label { text: "封面大小"; Layout.fillWidth: true } NodeSlider { objectName: "coverSlider"; value: coverSize; Layout.preferredWidth: 260; onMoved: { coverSize=Math.round(value); columnCount=0 } } }
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
                AppButton { text: "设置 DeepSeek API Key"; Layout.fillWidth: true; onClicked: { settingsDialog.close(); matchWindow.openAiSettings() } }
                AppButton { text: "重新运行设置向导"; Layout.fillWidth: true; onClicked: { settingsDialog.close();win.openSetup() } }
                Label { text: "目录存在不代表已有进度。未玩过的游戏可在首次保存后重新查找；多候选需要核对。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            }
        }
        footer: DialogButtonBox {
            AppButton { text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            AppButton { text: "保存本机设置"; enabled: !backend.busy; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole }
            onRejected: { coverSize=backend.settings.cover_size; columnCount=backend.settings.columns; gridGap=backend.settings.gap; installedOnly=backend.settings.installed_only; settingsDialog.close() }
            onAccepted: {
                backend.saveSettings({playnite:playnitePath.text, library:libraryPath.text, snapshots:snapshotPath.text, watch:watchSwitch.checked,watch_upload:autoUpload.checked,close_to_tray:traySwitch.checked,watch_interval:watchInterval.value}); saveLayout(); settingsDialog.close()
            }
        }
    }

    GameSettingsDialog {
        id: gameDialog; anchors.centerIn: parent
        onCloudRequested: cloudWindow.openConnectionSettings()
        onMatchRequested: function(ident) { win.openMatch(ident) }
        onHistoryRequested: function(ident) { win.activeId=ident;historyTabs.currentIndex=0;backend.history(ident);historyDialog.open() }
        onEnrichmentRequested: function(ident) { win.openEnrichment([ident],{},true) }
    }
    Dialog {
        id: deleteDialog; title: "移除 " + activeName; anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "只移除管理条目，保留游戏文件和已有快照。" }
        onAccepted: backend.remove(activeId)
    }
    Dialog {
        id: historyDialog; objectName: "historyDialog"; title: activeName + " · 存档记录"; anchors.centerIn: parent; width: Math.min(900,win.width-60); height: Math.min(650,win.height-60); modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ColumnLayout {
            RowLayout {
                IconButton { iconName: "cloud"; transferState: backend.transferStates[activeId] || "idle"; hoverEnabled: false; focusPolicy: Qt.NoFocus }
                Label { text: (backend.transferStates[activeId] || "idle")==="saving" ? "正在保存本地备份…" : backend.transferStates[activeId]==="uploading" ? "本地已保存，正在上传…" : backend.transferStates[activeId]==="success" ? "云端上传成功" : backend.transferStates[activeId]==="failed" ? "上传失败，本地备份保留，可补传" : "本地备份完成后再上传"; Layout.fillWidth: true; color: Theme.secondary }
            }
            RowLayout {
                enabled: !backend.busy
                AppButton { text: "保存本地 + 上传"; onClicked: backend.cloudSave(activeId) }
                AppButton { text: "仅本地备份"; onClicked: backend.localSave(activeId) }
                AppButton { text: "重试上传"; onClicked: backend.retry(activeId) }
                AppButton { text: "刷新记录"; onClicked: { if(historyTabs.currentIndex===0) backend.history(activeId); else backend.refreshCloudHistory(activeId) } }
            }
            TabBar { id: historyTabs; Layout.fillWidth: true; TabButton { text: "本机版本" } TabButton { text: "云端 / 其他设备" } }
            Label { text: historyTabs.currentIndex===0 ? "按时间从新到旧排列，恢复前先备份当前存档。" : "点击刷新读取云端版本；选择恢复时下载并校验，不自动覆盖本机。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            ListView {
                Layout.fillWidth: true; Layout.fillHeight: true; model: historyTabs.currentIndex===0 ? backend.snapshots : backend.cloudSnapshots; clip: true
                delegate: ItemDelegate {
                    required property var modelData
                    width: ListView.view.width; height: 84
                    contentItem: RowLayout {
                        ColumnLayout {
                            Layout.fillWidth: true
                            Label { text: modelData.created_at; Layout.fillWidth: true; elide: Text.ElideRight }
                            Label { text: (historyTabs.currentIndex===0 ? (modelData.uploaded ? "已上传" : "仅本地") : (modelData.computer || "云端版本")) + "  ·  " + (modelData.note || "无备注"); Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary; font.pixelSize: 12 }
                        }
                        AppButton { text: "备注"; visible: historyTabs.currentIndex===0; enabled: !backend.busy; onClicked: { noteDialog.snapshotId=modelData.id; snapshotNote.text=modelData.note || ""; noteDialog.open() } }
                        AppButton { text: historyTabs.currentIndex===0 ? "恢复" : "下载并恢复"; enabled: !backend.busy; onClicked: { restoreDialog.snapshotId=modelData.id || 0; restoreDialog.cloudRecord=historyTabs.currentIndex===1 ? modelData : ({}); restoreDialog.open() } }
                    }
                }
                ScrollBar.vertical: ScrollBar {}
                Label { visible: parent.count===0; anchors.centerIn: parent; text: historyTabs.currentIndex===0 ? "暂无本机记录，先创建一份备份。" : "点击刷新记录，查看云端版本。"; color: Theme.secondary }
            }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        }
        standardButtons: Dialog.Close
    }
    Dialog {
        id: noteDialog; property int snapshotId: 0; title: "存档备注"; anchors.centerIn: parent; width: Math.min(560,win.width-60); modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: AppTextField { id: snapshotNote; placeholderText: "例如：第三章结束，困难模式"; maximumLength: 1000 }
        standardButtons: Dialog.Save | Dialog.Cancel
        onAccepted: backend.setSnapshotNote(activeId,snapshotId,snapshotNote.text)
    }
    Dialog {
        id: restoreDialog; property int snapshotId: 0; property var cloudRecord: ({}); anchors.centerIn: parent; modal: true
        Overlay.modal: Rectangle { color: "#bb000000" }
        title: cloudRecord.remote ? "下载并恢复云端版本" : "恢复快照 #" + snapshotId; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "将替换本机已配置目录中的存档。当前存档会先另行备份。" }
        onAccepted: { if(cloudRecord.remote) backend.restoreCloudSnapshot(activeId,cloudRecord); else backend.restore(activeId, snapshotId) }
    }
}
