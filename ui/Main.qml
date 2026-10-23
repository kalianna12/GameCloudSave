import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "LibraryFilters.js" as Filters

ApplicationWindow {
    id: win
    visible: true
    width: 1440; height: 940
    minimumWidth: 900; minimumHeight: 650
    title: "GameCloudSave · V2.5.0"
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
    property int homeCoverSize: backend.settings.home_cover_size || 176
    property int homeGap: backend.settings.home_gap || 14
    property bool homeRecentPreview: backend.settings.home_recent_preview !== false
    readonly property string libraryDesign: backend.settings.library_design || "classic"
    readonly property bool alternativeDesign: libraryDesign!=="classic"
    onLibraryDesignChanged: if(libraryReady) Qt.callLater(function() { home.resetSelection();gridScroll.stop();grid.currentIndex=grid.count ? 0 : -1;grid.contentY=0 })
    property bool installedOnly: backend.settings.installed_only
    property string searchQuery: ""
    property string platformFilter: "all"
    property string importSourceFilter: "all"
    property string libraryMode: "home"
    property string groupFilter: ""
    property string seriesFilter: ""
    property string librarySort: "name"
    property var facets: ({series:"",tags:[],year:""})
    readonly property int activeFacetCount: Filters.count(facets)
    property var randomBag: []
    property string randomPoolKey: ""
    property bool libraryReady: false
    property bool fullScreenMode: !!backend.settings.fullscreen
    property int restoreVisibility: Window.Windowed
    function toggleFullScreen() { if(launchTransition.running) return;fullScreenMode=!fullScreenMode;backend.saveLayout({fullscreen:fullScreenMode}) }
    function applyFullScreen() {
        if(fullScreenMode) {
            if(visibility===Window.FullScreen) return
            if(visibility===Window.Maximized || visibility===Window.Windowed) restoreVisibility=visibility
            showFullScreen()
        } else if(restoreVisibility===Window.Maximized) { if(visibility!==Window.Maximized) showMaximized() }
        else if(visibility!==Window.Windowed) showNormal()
    }
    property double lastWindowRestore: 0
    function restoreLibraryWindow() {
        var now=Date.now();if(now-lastWindowRestore<180) return;lastWindowRestore=now
        windowStateApply.stop()
        var restoring=visibility===Window.Hidden || visibility===Window.Minimized
        if(restoring) { if(restoreVisibility===Window.Maximized) showMaximized();else showNormal() }
        else if(fullScreenMode && visibility!==Window.FullScreen) showFullScreen()
        if(!active) { raise();requestActivate() }
        if(restoring && fullScreenMode) restoreFullscreenFinish.restart()
    }
    function returnFromTool() {
        // Closing a tool while showing the desktop must not restore/raise the library.
        if(visibility===Window.Hidden || visibility===Window.Minimized || Qt.application.state!==Qt.ApplicationActive) return
        if(!active) requestActivate()
        if(fullScreenMode && visibility!==Window.FullScreen) restoreFullscreenFinish.restart()
    }
    Timer { id: restoreFullscreenFinish; interval: 70; onTriggered: if(win.active && win.visible && win.visibility!==Window.Minimized && win.fullScreenMode) win.applyFullScreen() }
    Timer { id: windowStateApply; interval: 35; onTriggered: if(win.visible && win.visibility!==Window.Minimized) win.applyFullScreen() }
    onFullScreenModeChanged: if(libraryReady) windowStateApply.restart()
    Shortcut { objectName: "fullscreenShortcut"; sequence: "F11"; autoRepeat: false; onActivated: win.toggleFullScreen() }
    Shortcut { sequence: "Escape"; enabled: launchTransition.running; onActivated: launchTransition.cancel() }
    Timer { id: launchFocusDelay; interval: 180; onTriggered: if(launchTransition.running) backend.launchFocusChanged() }
    onActiveChanged: if(!active && launchTransition.running) launchFocusDelay.restart()
    onVisibilityChanged: function(nextVisibility) {
        if(libraryReady && !fullScreenMode && (nextVisibility===Window.Maximized || nextVisibility===Window.Windowed)) restoreVisibility=nextVisibility
        if(libraryReady && launchTransition.running && (nextVisibility===Window.Hidden || nextVisibility===Window.Minimized)) launchTransition.cancel()
    }
    property int filterFocusIndex: 0
    property int headerFocusIndex: 0
    property var toolbarFocusItem: null
    property bool toolbarFocusMove: false
    property real toolbarColumnX: 0
    property real toolbarViewportWidth: 0
    onActiveFocusItemChanged: if(!toolbarFocusMove) toolbarFocusItem=null
    readonly property var filterControls: [installedControl,platformControl,sourceControl,facetControl,clearFacetsControl,randomControl,sortControl,mappingProfileControl,layoutControl,recommendationsControl,personalControl,fullscreenControl]
    readonly property var headerControls: [backButton,search,watchControl]
    property var navigationHistory: []
    property var toolbarReturn: null
    property string sidebarOrigin: ""
    function revealSidebar(control) { var flick=sidebarScroll.contentItem;if(!control || !flick.contentItem) return;var y=control.mapToItem(flick.contentItem,0,0).y;flick.contentY=Math.max(0,Math.min(Math.max(0,flick.contentHeight-flick.height),y<flick.contentY ? y-4 : y+control.height>flick.contentY+flick.height ? y+control.height-flick.height+4 : flick.contentY)) }
    function focusSidebar(index) { sidebarOrigin=libraryMode;var items=[navHome,navAll,navRecent,navFavorites,navSeries,navNew,navEnrichment,navAchievements,navMapping];focusControls(items,index);revealSidebar(items[index]) }
    function rememberNavigationFocus() { return {content:libraryFocus(),item:activeFocusItem} }
    function restoreNavigationFocus() {
        var saved=toolbarReturn;toolbarReturn=null
        if(saved && !saved.content && saved.item && saved.item.visible && saved.item.enabled) saved.item.forceActiveFocus()
        else focusContent()
    }
    function toggleToolbar() {
        if(toolbarReturn) { restoreNavigationFocus();return }
        toolbarReturn=rememberNavigationFocus();focusToolbar(search,false)
    }
    function goBack() {
        var previous=navigationHistory.length ? navigationHistory[navigationHistory.length-1] : {mode:"home",category:"",series:"",search:"",y:0,gridY:0,gridIndex:0}
        navigationHistory=navigationHistory.slice(0,-1)
        searchDelay.stop();search.text=previous.search;searchQuery=previous.search;searchDelay.stop()
        libraryMode=previous.mode;librarySort=previous.sort || (previous.mode==="recent" ? "recent" : previous.mode==="new" ? "added" : "name");groupFilter=previous.category;seriesFilter=previous.series
        Qt.callLater(function() { if(win.alternativeDesign) win.focusContent();else if(win.homeVisible) home.restorePosition(previous.y);else { grid.currentIndex=Math.min(grid.count-1,previous.gridIndex || 0);grid.contentY=previous.gridY || 0;grid.forceActiveFocus() } })
    }
    function libraryFocus() {
        var item=activeFocusItem
        while(item) { if(item===home || item===grid || item===experienceLoader.item) return true;item=item.parent }
        return !activeFocusItem || activeFocusItem===contentItem
    }
    function focusContent() { if(alternativeDesign && experienceLoader.item) experienceLoader.item.focusContent();else if(homeVisible) home.resumeFocus();else { grid.forceActiveFocus();if(grid.count) grid.navigateFocus(Math.max(0,grid.currentIndex)) } }
    function focusFirstContent() { if(alternativeDesign && experienceLoader.item) experienceLoader.item.focusFirst();else if(homeVisible) home.focusFirst();else if(grid.count) grid.navigateFocus(0);else grid.forceActiveFocus() }
    function previewSidebar(index) {
        var modes=["home","all","recent","favorites","series","new"]
        if(index<0 || index>=modes.length) return false
        if(libraryMode===modes[index] && !searchQuery && !search.text && !groupFilter && !seriesFilter) return false
        resetGridSelection=true
        searchDelay.stop();search.text="";searchDelay.stop();searchQuery="";groupFilter="";seriesFilter=""
        libraryMode=modes[index];librarySort=libraryMode==="recent" ? "recent" : libraryMode==="new" ? "added" : "name"
        grid.currentIndex=grid.count ? 0 : -1;grid.contentY=0
        if(homeVisible && libraryDesign==="classic") home.resetSelection()
        return true
    }
    function focusControls(items,index) {
        var available=items.filter(function(item) { return item.visible && item.enabled })
        if(available.length) { available[Math.max(0,Math.min(available.length-1,index))].forceActiveFocus();backend.navigationMoved() }
    }
    function toolbarRows(controls) {
        var positions=controls.filter(function(item) { return item.visible && item.enabled && item.width>0 && item.height>0 }).map(function(item) {
            var p=item.mapToItem(win.contentItem,item.width/2,item.height/2)
            return {item:item,x:p.x,y:p.y,height:item.height}
        }).sort(function(a,b) { return a.y-b.y || a.x-b.x }),rows=[]
        positions.forEach(function(position) {
            var row=rows.length ? rows[rows.length-1] : null
            if(!row || Math.abs(position.y-row.y)>=Math.min(position.height,row.height)/2) { row={y:position.y,height:position.height,items:[]};rows.push(row) }
            row.items.push(position)
        })
        rows.forEach(function(row) { row.items.sort(function(a,b) { return a.x-b.x }) })
        return rows
    }
    function focusToolbar(control,keepColumn) {
        if(!keepColumn || toolbarViewportWidth!==win.width) toolbarColumnX=control.mapToItem(win.contentItem,control.width/2,0).x
        toolbarFocusItem=control;toolbarViewportWidth=win.width
        var filters=filterControls.filter(function(item) { return item.visible && item.enabled }),headers=headerControls.filter(function(item) { return item.visible && item.enabled })
        if(filters.indexOf(control)>=0) filterFocusIndex=filters.indexOf(control)
        if(headers.indexOf(control)>=0) headerFocusIndex=headers.indexOf(control)
        toolbarFocusMove=true;control.forceActiveFocus();toolbarFocusMove=false;backend.navigationMoved()
    }
    function closestToolbarItem(row,x) {
        return row.items.reduce(function(best,entry) { return !best || Math.abs(entry.x-x)<Math.abs(best.x-x) ? entry : best },null).item
    }
    function focusToolbarFromContent() {
        var filters=filterControls.filter(function(item) { return item.visible && item.enabled }),rows=toolbarRows(filters)
        if(!rows.length) return
        var previous=filters[Math.max(0,Math.min(filters.length-1,filterFocusIndex))]
        toolbarColumnX=previous.mapToItem(win.contentItem,previous.width/2,0).x;toolbarViewportWidth=win.width
        focusToolbar(closestToolbarItem(rows[rows.length-1],toolbarColumnX),true)
    }
    function controllerInput(command) {
        if(!win.active || backend.popupActive()) return false
        if(launchTransition.running) return launchTransition.controllerInput(command)
        if(command==="zoom-in" || command==="zoom-out") { if(libraryDesign==="atlas" && libraryFocus() && experienceLoader.item) experienceLoader.item.controllerInput(command);return true }
        if(command==="search") { toggleToolbar();return true }
        if(command==="back") {
            if(toolbarReturn) { restoreNavigationFocus();return true }
            if(!libraryFocus()) { focusContent();return true }
            if(alternativeDesign && experienceLoader.item && experienceLoader.item.controllerBack()) return true
            if(libraryMode!=="home" || searchQuery || navigationHistory.length) goBack()
            else navHome.forceActiveFocus()
            return true
        }
        var sidebar=[navHome,navAll,navRecent,navFavorites,navSeries,navNew,navEnrichment,navAchievements,navMapping]
        var filters=filterControls.filter(function(control) { return control.visible && control.enabled })
        var headers=headerControls.filter(function(control) { return control.visible && control.enabled })
        var item=activeFocusItem,side=-1,filter=-1,header=-1
        while(item) { if(side<0) side=sidebar.indexOf(item);if(filter<0) filter=filters.indexOf(item);if(header<0) header=headers.indexOf(item);item=item.parent }
        if(side>=0) {
            if(command==="right" || command==="activate") { if(command==="right" && sidebarOrigin===libraryMode) focusContent();else if(side>=6 && command==="activate") sidebar[side].clicked();else { var changed=previewSidebar(side);if(changed) focusFirstContent();else focusContent() };sidebarOrigin="";return true }
            if(command==="up" || command==="down") { sidebarOrigin="";var nextSide=Math.max(0,Math.min(sidebar.length-1,side+(command==="up" ? -1 : 1)));focusControls(sidebar,nextSide);revealSidebar(sidebar[nextSide]);previewSidebar(nextSide);return true }
            return true
        }
        if(filter>=0 || header>=0) {
            var current=filter>=0 ? filters[filter] : headers[header],rows=toolbarRows(headers.concat(filters)),rowIndex=-1,columnIndex=-1
            rows.forEach(function(row,i) { row.items.forEach(function(entry,j) { if(entry.item===current) { rowIndex=i;columnIndex=j } }) })
            if(rowIndex<0) return true
            if(toolbarFocusItem!==current || toolbarViewportWidth!==win.width) { toolbarColumnX=current.mapToItem(win.contentItem,current.width/2,0).x;toolbarFocusItem=current;toolbarViewportWidth=win.width }
            if(filter>=0) filterFocusIndex=filter;else headerFocusIndex=header
            if(command==="up" || command==="down") {
                var destination=rowIndex+(command==="up" ? -1 : 1)
                if(destination>=0 && destination<rows.length) focusToolbar(closestToolbarItem(rows[destination],toolbarColumnX),true)
                else if(command==="down") focusContent()
                return true
            }
            if(command==="left" || command==="previous" || command==="right" || command==="next") {
                var step=(command==="left" || command==="previous") ? -1 : 1
                if(columnIndex===0 && step<0) { var sideIndex=Math.max(0,["home","all","recent","favorites","series","new"].indexOf(libraryMode));focusSidebar(sideIndex) }
                else focusToolbar(rows[rowIndex].items[Math.max(0,Math.min(rows[rowIndex].items.length-1,columnIndex+step))].item,false)
                return true
            }
            if(command==="activate") {
                if(header>=0 && headers[header]===search) { searchKeyboard.start(search.text);return true }
                if(header>=0 && headers[header]===watchControl) { watchControl.toggle();watchControl.toggled();return true }
                if(filter>=0 && filters[filter]===installedControl) { installedControl.toggle();installedControl.toggled();return true }
                if(header>=0 && headers[header]===backButton) goBack()
                if(filter>=0 && filters[filter]===fullscreenControl) win.toggleFullScreen()
                if(filter>=0 && filters[filter]===personalControl) personalControl.clicked()
                if(filter>=0 && filters[filter]===layoutControl) layoutControl.clicked()
                if(filter>=0 && filters[filter]===facetControl) facetControl.clicked()
                if(filter>=0 && filters[filter]===clearFacetsControl) clearFacetsControl.clicked()
                if(filter>=0 && filters[filter]===randomControl) randomControl.clicked()
                if(filter>=0 && filters[filter]===recommendationsControl) recommendationsControl.clicked()
            }
            return true
        }
        if(alternativeDesign && experienceLoader.item) return experienceLoader.item.controllerInput(command)
        if(command==="next" || command==="previous") {
            if(!libraryFocus()) focusContent()
            var pageDirection=command==="next" ? 1 : -1
            if(homeVisible) home.pageSelection(pageDirection)
            else if(grid.count) grid.navigateFocus(Math.max(0,Math.min(grid.count-1,grid.currentIndex+pageDirection*grid.effectiveColumns*Math.max(1,Math.floor(grid.height/grid.cellHeight)))))
            return true
        }
        if(!libraryFocus()) {
            if(["up","down","left","right"].indexOf(command)<0) return true
            focusContent()
        }
        if(!homeVisible) grid.adoptFocusedCard()
        if(command==="left" && (homeVisible ? home.selectionIndex()<=0 : grid.currentIndex<=0 || grid.currentIndex%grid.effectiveColumns===0)) { var sideIndex=Math.max(0,["home","all","recent","favorites","series","new"].indexOf(libraryMode));focusSidebar(sideIndex);return true }
        if(command==="up" && (homeVisible ? home.atTop : grid.currentIndex<grid.effectiveColumns)) { focusToolbarFromContent();return true }
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
        if(command==="activate") win.launchGame(game)
        else if(command==="favorite") backend.toggleFavorite(game.id)
        else if(command==="menu") controllerGameMenu.showGame(game)
        else if(command==="history") { selectGame(game);historyTabs.currentIndex=0;backend.history(game.id);historyDialog.open() }
        else return false
        return true
    }
    ListModel { id: libraryModel;objectName: "gameLibraryRecords"; dynamicRoles: true }
    QtObject {
        id: searchDelay
        function restart() { backend.scheduleLibrarySearch(search.text) }
        function stop() { backend.cancelLibrarySearch() }
    }
    Connections { target: backend;function onLibrarySearchReady(value) { win.searchQuery=value } }
    property var seriesNames: { var revision=backend.libraryRevision;return ((backend.libraryGroups().find(function(section) { return section.id==="series" }) || {}).items || []).map(function(item) { return item.name }) }
    property var searchTokens: searchQuery.split(/[,，\s]+/).map(function(token) { return token.replace(/^#/,'') }).filter(Boolean)
    property bool homeVisible: libraryMode==="home" && searchTokens.length===0 && (shownGames.length>0 || !activeFacetCount && backend.settings.recommendations_enabled!==false)
    property var localHomeRows: { var revision=backend.libraryRevision;return backend.homeSections(installedOnly,platformFilter,importSourceFilter,facets).filter(function(section) { return section.items.length>0 }) }
    property var homeRows: {
        var local=localHomeRows
        var recommendations=!activeFacetCount && backend.settings.recommendations_enabled!==false ? backend.recommendations.sections : []
        var split=local.length>1 && local[1].id==="new" ? 2 : 1
        return local.slice(0,split).concat(recommendations,local.slice(split))
    }
    property var gameSnapshot: { var revision=backend.libraryRevision;return backend.libraryGames() }
    property var scopedGames: gameSnapshot.filter(function(g) { return (!installedOnly || g.installed) && (platformFilter==="all" || (g.platform || "local")===platformFilter || platformFilter==="local" && g.platform==="other") && (importSourceFilter==="all" || g.import_source===importSourceFilter) && searchTokens.every(function(token) { return (g.searchText || g.name.toLowerCase()).indexOf(token)>=0 }) && (libraryMode!=="new" || g.isNew) && (libraryMode!=="favorites" || g.favorite) && (libraryMode!=="recent" || g.last_played) && (libraryMode!=="group" || (g.groups || []).indexOf(groupFilter)>=0) && (libraryMode!=="category" || g.category===groupFilter) && (libraryMode!=="series" || seriesNames.indexOf(g.series)>=0 && (!seriesFilter || g.series===seriesFilter)) })
    property var shownGames: scopedGames.filter(function(game) { return Filters.matches(game,facets) }).sort(function(a,b) { if(librarySort==="release_asc" || librarySort==="release_desc") {
        var ad=a.release_date || "",bd=b.release_date || ""
        if(!ad || !bd) return ad ? -1 : bd ? 1 : a.name.localeCompare(b.name)
        return (librarySort==="release_asc" ? ad.localeCompare(bd) : bd.localeCompare(ad)) || a.name.localeCompare(b.name)
    }
    return librarySort==="recent" ? (b.last_played || "").localeCompare(a.last_played || "") || a.name.localeCompare(b.name) : librarySort==="added" ? (b.added_at || "").localeCompare(a.added_at || "") || a.name.localeCompare(b.name) : a.name.localeCompare(b.name) })
    function setFacets(values) {
        resetGridSelection=true;facets={series:values.series || "",tags:(values.tags || []).slice(),year:values.year || ""};randomBag=[]
        Qt.callLater(function() { win.focusFirstContent() })
    }
    function randomGame() {
        if(!shownGames.length) return
        var key=shownGames.map(function(game) { return game.id }).sort().join("\u0001")
        if(key!==randomPoolKey) { randomPoolKey=key;randomBag=[] }
        if(!randomBag.length) {
            randomBag=shownGames.map(function(game) { return game.id })
            for(var i=randomBag.length-1;i>0;i--) { var j=Math.floor(Math.random()*(i+1)),id=randomBag[i];randomBag[i]=randomBag[j];randomBag[j]=id }
            if(randomBag.length>1 && randomBag[randomBag.length-1]===randomDialog.game.id) { var first=randomBag[0];randomBag[0]=randomBag[randomBag.length-1];randomBag[randomBag.length-1]=first }
        }
        var next=randomBag[randomBag.length-1];randomBag=randomBag.slice(0,-1);randomControl.animateRoll()
        randomDialog.begin(shownGames.find(function(game) { return game.id===next }),shownGames.length)
    }
    function navigate(mode,value) {
        resetGridSelection=true
        navigationHistory=navigationHistory.slice(-29).concat([{mode:libraryMode,category:groupFilter,series:seriesFilter,search:searchQuery,y:home.contentPosition(),gridY:grid.contentY,gridIndex:grid.currentIndex,sort:librarySort}])
        search.text="";searchQuery="";groupFilter="";seriesFilter=""
        if(mode==="tag") { libraryMode="all";search.text="#"+value;searchQuery=search.text.toLowerCase() }
        else { libraryMode=mode;librarySort=mode==="recent" ? "recent" : mode==="new" ? "added" : "name";if(mode==="category") groupFilter=value;if(mode==="series") seriesFilter=value }
        Qt.callLater(function() { win.focusFirstContent() })
    }
    onShownGamesChanged: if(libraryReady) Qt.callLater(win.syncLibrary)
    property var librarySignatures: ({})
    property var libraryOrder: []
    property bool resetGridSelection: false
    function syncLibrary() {
        var signatures={},order=libraryOrder.slice(),selectedId=!resetGridSelection && grid.currentIndex>=0 && grid.currentIndex<libraryModel.count ? libraryModel.get(grid.currentIndex).record.id : ""
        for(var i=0;i<shownGames.length;i++) {
            var signature=JSON.stringify(shownGames[i]);signatures[shownGames[i].id]=signature
            var position=order.indexOf(shownGames[i].id,i)
            if(position<0) { libraryModel.insert(i,{record:shownGames[i]});order.splice(i,0,shownGames[i].id) }
            else {
                if(position!==i) { libraryModel.move(position,i,1);order.splice(i,0,order.splice(position,1)[0]) }
                if(librarySignatures[shownGames[i].id]!==signature) libraryModel.setProperty(i,"record",shownGames[i])
            }
        }
        if(libraryModel.count>shownGames.length) libraryModel.remove(shownGames.length,libraryModel.count-shownGames.length)
        libraryOrder=order.slice(0,shownGames.length);librarySignatures=signatures
        if(resetGridSelection) { grid.currentIndex=libraryModel.count ? 0 : -1;resetGridSelection=false;return }
        var current=shownGames.findIndex(function(g) { return g.id===selectedId });if(current>=0) grid.currentIndex=current
    }
    onClosing: function(close) { if(launchTransition.running) launchTransition.cancel();if(backend.closeToTray()) { close.accepted=false; cloudWindow.hide(); matchWindow.hide(); importWindow.hide(); batchWindow.hide();setupWizard.hide();libraryManager.hide();personalization.hide();mappingWindow.hide();enrichmentWindow.hide();achievementsWindow.hide();hide() } else Qt.quit() }
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
        autoKeep.value=s.auto_snapshot_keep || 5
        recommendationsToggle.checked=s.recommendations_enabled!==false
        steamRecommendations.checked=s.recommendations_steam!==false;xboxRecommendations.checked=s.recommendations_xbox!==false
        traySwitch.checked=s.close_to_tray; watchInterval.value=s.watch_interval
        settingsTabs.currentIndex=typeof page==="number" ? page : 0
        settingsDialog.open()
    }
    function openCloud() { guideDialog.close(); cloudWindow.openBrowser() }
    function openMatch(ident) { guideDialog.close(); matchWindow.openMatcher(ident || "") }
    function openSaveSearch(ids) { if(ids.length) { guideDialog.close();matchWindow.openForGames(ids) } }
    function openImport() { guideDialog.close(); importWindow.openImporter() }
    function openBatch() { guideDialog.close();batchWindow.openBatch() }
    function openSetup() { guideDialog.close();setupWizard.openWizard() }
    function restoreLayout() { var s=backend.settings;coverSize=s.cover_size;columnCount=s.columns;gridGap=s.gap;installedOnly=s.installed_only;homeCoverSize=s.home_cover_size || 176;homeGap=s.home_gap || 14;homeRecentPreview=s.home_recent_preview!==false }
    function saveLayout() { backend.saveLayout({cover_size:coverSize, columns:columnCount, gap:gridGap, installed_only:installedOnly,home_cover_size:homeCoverSize,home_gap:homeGap,home_recent_preview:homeRecentPreview}) }
    ControllerKeyboard {
        id: searchKeyboard; objectName: "controllerKeyboard"
        width: Math.min(1600,win.width-48); anchors.centerIn: parent
        backdropUrl: { var game=win.alternativeDesign && experienceLoader.item ? experienceLoader.item.selectedGame : win.homeVisible ? home.selectedGame() : grid.count ? libraryModel.get(Math.max(0,grid.currentIndex)).record : null;return game ? game.backgroundUrl || game.coverHighUrl || game.coverUrl || "" : "" }
        onSubmitted: function(value) { win.toolbarReturn=null;search.text=value;searchDelay.stop();win.searchQuery=value.trim().toLowerCase();Qt.callLater(win.focusContent) }
        onCancelled: search.forceActiveFocus()
        onReturned: win.restoreNavigationFocus()
    }
    LibraryFilterDialog { id: facetDialog;anchors.centerIn: parent;games: win.scopedGames;onCriteriaApplied: function(values) { win.setFacets(values) } }
    RandomGameDialog {
        id: randomDialog;anchors.centerIn: parent
        onRedrawRequested: win.randomGame()
        onLaunchRequested: function(game) { win.launchGame(game) }
        onSettingsRequested: function(game) { win.selectGame(game);gameDialog.openFor(game.id,0) }
        onClosed: Qt.callLater(function() { if(win.active && !backend.popupActive() && !launchTransition.running) randomControl.forceActiveFocus() })
    }
    ControllerGameMenu { id: controllerGameMenu; anchors.centerIn: parent; width: Math.min(600,win.width-48); useLaunchTransition: true; onLaunchRequested: function(game) { win.launchGame(game) } onSettingsRequested: function(game) { win.selectGame(game);gameDialog.openFor(game.id,0) } onGraphicsRequested: function(game) { win.selectGame(game);gameDialog.openFor(game.id,3) } }
    function launchGame(game) {
        if(!game || !game.id || backend.busy || launchTransition.running) return
        launchTransition.begin(game,libraryDesign)
    }
    LaunchTransition { id: launchTransition; anchors.fill: parent; z: 500; onCommitted: function(game) { backend.launch(game.id) } }
    EnrichmentWindow { id: enrichmentWindow;onSaveSearchRequested: function(ids) { if(ids.length) { hide();win.openSaveSearch(ids) } } onAchievementsRequested: function(ids) { achievementsWindow.openFor(ids) } }
    AchievementsWindow { id: achievementsWindow;objectName: "achievementsWindow" }
    Connections { target: backend; function onEnrichmentRequested(ids,options) { win.openEnrichment(ids,options,true) } }
    CloudWindow { id: cloudWindow; objectName: "cloudWindow" }
    ImportWindow { id: importWindow; objectName: "importWindow" }
    BatchWindow { id: batchWindow; objectName: "batchWindow" }
    SetupWizard { id: setupWizard; objectName: "setupWizard" }
    LibraryManager { id: libraryManager; objectName: "libraryManager" }
    PersonalizationWindow { id: personalization; objectName: "personalization"; onReturnRequested: Qt.callLater(function() { win.returnFromTool();if(win.active) personalControl.forceActiveFocus() }) }
    InputMappingWindow { id: mappingWindow; onReturnRequested: Qt.callLater(function() { win.returnFromTool();if(win.visible && win.visibility!==Window.Minimized) win.focusContent() }) }
    MatchWindow { id: matchWindow; objectName: "matchWindow"; onBatchRequested: win.openBatch() }
    Component.onCompleted: { backend.prepareLibraryWindow(win);backend.mapping.bindRuntimeWindow(win);libraryReady=true;syncLibrary();if(fullScreenMode) applyFullScreen();if(!backend.settings.setup_completed) setupWizard.openWizard();else if(!backend.settings.guide_dismissed) guideDialog.open() }


    Rectangle {
        width: 200; anchors.top: parent.top; anchors.bottom: parent.bottom
        color: Theme.sidebar
        Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Theme.outline }
        Row {
            x: 18; y: 25; spacing: 10
            Image { source: "icons/app.svg"; width: 30; height: 30; sourceSize: Qt.size(90,90) }
            Label { text: "GameCloudSave"; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: 13; font.weight: Font.DemiBold; color: Theme.text }
        }
        ScrollView { id: sidebarScroll;anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 84; bottom: parent.bottom; bottomMargin: 80 }
            clip: true
            Column { x: 8; spacing: 4
                NavigationButton { id: navHome; objectName: "navHome"; width: 184; iconName: "grid"; text: "游戏库主页"; selected: libraryMode==="home"; onClicked: win.navigate("home","") }
                NavigationButton { id: navAll; objectName: "navAll"; width: 184; iconName: "grid"; text: "全部游戏"; selected: libraryMode==="all"; onClicked: win.navigate("all","") }
                NavigationButton { id: navRecent; objectName: "navRecent"; width: 184; iconName: "play"; text: "最近游玩"; selected: libraryMode==="recent"; onClicked: win.navigate("recent","") }
                NavigationButton { id: navFavorites; objectName: "navFavorites"; width: 184; iconName: "star"; text: "收藏"; selected: libraryMode==="favorites"; onClicked: win.navigate("favorites","") }
                NavigationButton { id: navSeries; objectName: "navSeries"; width: 184; iconName: "folder"; text: "系列"; selected: libraryMode==="series"; onClicked: win.navigate("series","") }
                NavigationButton { id: navNew;objectName: "navNew";width: 184;iconName: "star";text: "新加入";selected: libraryMode==="new";onClicked: win.navigate("new","") }
                Item { width: 184; height: 18; Rectangle { anchors.centerIn: parent; width: 160; height: 1; color: Theme.outline } }
                NavigationButton { id: navEnrichment;objectName: "enrichmentNav"; width: 184; iconName: "spark"; text: "资料补全"; onClicked: win.openEnrichment([],{},false) }
                NavigationButton { id: navAchievements;objectName: "achievementsNav";width: 184;iconName: "achievement";text: "成就管理";onClicked: achievementsWindow.openFor([]) }
                NavigationButton { id: navMapping; objectName: "mappingNav"; width: 184; iconName: "settings"; text: "手柄映射"; onClicked: mappingWindow.openMapping() }
                NavigationButton { width: 184; iconName: "cloud"; text: "云端存储"; onClicked: win.openCloud() }
                NavigationButton { width: 184; iconName: "folder"; text: "查找存档"; onClicked: win.openMatch("") }
                NavigationButton { width: 184; iconName: "help"; text: "使用指南"; onClicked: guideDialog.open() }
                NavigationButton { width: 184; iconName: "settings"; text: "管理分类与系列"; onClicked: libraryManager.openManager() }
            }
        }
        NavigationButton { x: 8; anchors.bottom: parent.bottom; anchors.bottomMargin: 20; iconName: "settings"; text: "设置"; onClicked: win.openSettings() }
    }

    ColumnLayout {
        anchors { left: parent.left; leftMargin: 232; right: parent.right; rightMargin: 32; top: parent.top; topMargin: 28; bottom: parent.bottom; bottomMargin: 18 }
        spacing: 20
        RowLayout {
            Layout.fillWidth: true
            AppButton { id: backButton; objectName: "libraryBack"; text: "返回"; visible: libraryMode!=="home" || searchTokens.length>0; onClicked: win.goBack() }
            RowLayout {
                spacing: 12
                Label { text: searchTokens.length ? "搜索结果" : libraryMode==="new" ? "新加入 · 近 3 天" : libraryMode==="home" ? "游戏库" : libraryMode==="favorites" ? "我的收藏" : libraryMode==="recent" ? "最近游玩" : libraryMode==="group" || libraryMode==="category" ? groupFilter : libraryMode==="series" ? "系列游戏" : "全部游戏"; font.pixelSize: win.width<1100 ? 23 : 28; font.weight: Font.DemiBold; color: Theme.text }
                Label { text: shownGames.length.toString(); color: Theme.secondary; font.pixelSize: 12; leftPadding: 9; rightPadding: 9; topPadding: 4; bottomPadding: 4; background: Rectangle { radius: 8; color: Theme.surface } }
            }
            Item { Layout.fillWidth: true }
            AppTextField {
                id: search;objectName: "search";clip: true;selectByMouse: true
                Keys.onEscapePressed: { if(!inputMethodComposing) { if(text) text="";else win.restoreNavigationFocus() } }
                onTextChanged: if(!inputMethodComposing) searchDelay.restart()
                onInputMethodComposingChanged: if(!inputMethodComposing) searchDelay.restart()
                placeholderText: "名称、拼音、首字母、标签";Layout.preferredWidth: win.width<1100 ? 165 : 260
            }
            Switch {
                id: watchControl; objectName: "watchControl"; text: "自动监听"; checked: backend.settings.watch; enabled: !backend.busy
                onToggled: backend.saveSettings({watch:checked})
                ToolTip.visible: !backend.controllerMode && hovered; ToolTip.text: backend.watchInfo.message
                Rectangle { objectName: "watchFocusRing"; anchors.fill: parent; anchors.margins: -3; z: 10; color: "transparent"; radius: 6; border.width: 3; border.color: Theme.accent; visible: watchControl.activeFocus }
            }
            AppButton { id: importControl; text: "导入游戏"; highlighted: true; onClicked: win.openImport() }
        }
        GridLayout {
            Layout.fillWidth: true; columns: win.width<1480 ? 1 : 2
            rowSpacing: 2; columnSpacing: 16
            Item {
                Layout.fillWidth: true;Layout.alignment: Qt.AlignTop;implicitHeight: filtersFlow.height
                Flow {
                id: filtersFlow;width: parent.width;height: childrenRect.height;spacing: 8
                CheckBox {
                    id: installedControl; objectName: "installedFilter"; text: "仅已安装"; checked: installedOnly
                    height: 38
                    onToggled: { installedOnly=checked; saveLayout() }
                    Rectangle {
                        objectName: "installedFocusRing"; anchors.fill: parent; anchors.margins: -3; z: 10
                        color: "transparent"; radius: 6; border.width: 3; border.color: Theme.accent
                        visible: installedControl.activeFocus
                    }
                }
                AppComboBox { id: platformControl; objectName: "platformFilter"; quiet: true; model: ["全部平台","Steam","Epic","Ubisoft","本地 / 其他"]; width: 130; onActivated: platformFilter=["all","steam","epic","ubisoft","local"][currentIndex] }
                AppComboBox { id: sourceControl; objectName: "sourceFilter"; quiet: true; model: ["全部来源","Playnite","游戏平台","本地扫描"]; width: 120; onActivated: importSourceFilter=["all","playnite","platform","folder"][currentIndex] }
                AppButton {
                    id: facetControl;objectName: "libraryFilterControl";width: activeFacetCount ? 106 : 84;height: 38
                    text: activeFacetCount ? "筛选 · "+activeFacetCount : "筛选";onClicked: facetDialog.begin(win.facets)
                    ToolTip.visible: hovered && !backend.controllerMode;ToolTip.text: activeFacetCount ? Filters.describe(win.facets) : "按系列、标签和发行年份筛选"
                    background: Rectangle { radius: Theme.controlRadius;color: facetControl.hovered ? Theme.hover : win.activeFacetCount ? Theme.selection : "transparent";border.width: facetControl.activeFocus ? 3 : win.activeFacetCount ? 1 : 0;border.color: Theme.accent }
                    contentItem: RowLayout {
                        spacing: 7
                        Canvas {
                            Layout.preferredWidth: 16;Layout.preferredHeight: 16
                            property color ink: Theme.text;onInkChanged: requestPaint()
                            onPaint: { var c=getContext("2d");c.reset();c.strokeStyle=ink;c.lineWidth=1.5;c.lineJoin="round";c.beginPath();c.moveTo(1,2);c.lineTo(15,2);c.lineTo(10,8);c.lineTo(10,13);c.lineTo(6,15);c.lineTo(6,8);c.closePath();c.stroke() }
                        }
                        Label { text: facetControl.text;color: Theme.text;font.pixelSize: 13 }
                    }
                }
                AppButton { id: clearFacetsControl;objectName: "clearLibraryFilters";visible: activeFacetCount>0;width: 92;height: 38;text: "清除筛选";flat: true;onClicked: win.setFacets({}) }
                DiceButton { id: randomControl;objectName: "homeRandomGame";visible: !win.alternativeDesign;enabled: win.shownGames.length>0 && !backend.busy && !launchTransition.running;onClicked: win.randomGame();ToolTip.visible: hovered && !backend.controllerMode;ToolTip.text: "从当前筛选范围随机挑选一款游戏" }
                }
            }
            Item {
                Layout.fillWidth: true;Layout.alignment: Qt.AlignTop;implicitWidth: actionsFlow.naturalWidth;implicitHeight: actionsFlow.height
                Flow {
                id: actionsFlow;anchors.right: parent.right;spacing: 10
                readonly property real naturalWidth: { var total=0,count=0;for(var i=0;i<children.length;i++) if(children[i].visible) { total+=children[i].width;count++ };return total+Math.max(0,count-1)*spacing }
                width: Math.min(parent.width,naturalWidth);height: childrenRect.height
                AppComboBox { id: sortControl; objectName: "librarySort"; quiet: true; currentIndex: ["name","recent","added","release_asc","release_desc"].indexOf(librarySort); visible: (!homeVisible || alternativeDesign) && libraryDesign!=="atlas"; model: ["名称排序","最近游玩","最近添加","发行日期: 从早到晚","发行日期: 从晚到早"]; width: Math.max(200,implicitWidth); onActivated: librarySort=["name","recent","added","release_asc","release_desc"][currentIndex] }
                AppComboBox {
                    id: mappingProfileControl;objectName: "homeMappingProfile";width: 240;model: backend.mapping.profileOptions;textRole: "label";wrapOptions: true
                    currentIndex: Math.max(0,backend.mapping.profileOptions.findIndex(function(p) { return p.id===backend.mapping.activeProfile }))
                    onActivated: backend.mapping.activateProfile(backend.mapping.profileOptions[currentIndex].id)
                    ToolTip.visible: hovered && !backend.controllerMode;ToolTip.text: currentText+"\n"+backend.mapping.state.message+"\n无 = 关闭；🎮→⌨ 手柄到键鼠，⌨→🎮 键鼠到手柄。"
                }
                AppButton { id: layoutControl; objectName: "layoutControl"; text: "布局"; flat: true; onClicked: win.openSettingsPage(2) }
                AppButton { id: recommendationsControl; objectName: "recommendationsControl"; text: "游戏推荐"; flat: true; visible: win.alternativeDesign && backend.settings.recommendations_enabled!==false; onClicked: recommendationDialog.open() }
                AppButton { id: personalControl; objectName: "personalControl"; text: "个性化"; flat: true; onClicked: personalization.openPersonalization() }
                AppButton { id: fullscreenControl; objectName: "fullscreenControl"; text: win.fullScreenMode ? "退出全屏" : "全屏"; flat: true; onClicked: win.toggleFullScreen(); ToolTip.visible: hovered && !backend.controllerMode; ToolTip.text: "F11 切换全屏" }
                }
            }
        }
        Loader {
            id: experienceLoader; objectName: "experienceLoader"; active: win.alternativeDesign; visible: active
            Layout.fillWidth: true; Layout.fillHeight: true
            sourceComponent: LibraryExperience {
                objectName: "libraryExperience"; design: win.libraryDesign; games: win.shownGames; coverSize: homeCoverSize; launching: launchTransition.running
        onBoundaryRequested: function(direction) { if(direction==="up") win.focusToolbarFromContent();else { var index=Math.max(0,["home","all","recent","favorites","series","new"].indexOf(win.libraryMode));win.focusSidebar(index) } }
                onDetailsRequested: function(game) { win.openGame(game) }
                onLaunchRequested: function(game) { win.launchGame(game) }
                onCloudRequested: function(game) { selectGame(game);historyTabs.currentIndex=0;backend.history(activeId);historyDialog.open() }
                onRemoveRequested: function(game) { selectGame(game);deleteDialog.open() }
            }
        }
        LibraryHome {
            id: home; objectName: "libraryHome"; visible: homeVisible && libraryDesign==="classic"
            Layout.fillWidth: true; Layout.fillHeight: true; sections: homeRows
            coverSize: homeCoverSize; cardGap: homeGap; recentPreview: homeRecentPreview
            onSaveSearchRequested: function(ids) { win.openSaveSearch(ids) }
            onBrowseRequested: function(mode,value) { win.navigate(mode,value) }
            onDetailsRequested: function(game) { win.openGame(game) }
            onLaunchRequested: function(game) { win.launchGame(game) }
            onCloudRequested: function(game) { selectGame(game);historyTabs.currentIndex=0;backend.history(activeId);historyDialog.open() }
        }
        GridView {
            id: grid
            objectName: "gameGrid"
            highlightFollowsCurrentItem: false
            activeFocusOnTab: true
            function adoptFocusedCard() {
                var item=win.activeFocusItem
                while(item && item!==grid) { if(item.libraryIndex!==undefined) { currentIndex=item.libraryIndex;return } item=item.parent }
            }
            function navigateFocus(index) {
                var previousIndex=currentIndex
                currentIndex=index
                var start=Math.floor(index/effectiveColumns)*cellHeight,destination=gridScroll.running ? gridScroll.to : contentY
                if(start<destination) destination=start
                else if(start+cellHeight>destination+height) destination=start+cellHeight-height
                destination=Math.max(originY,Math.min(Math.max(originY,contentHeight-height),destination))
                if(win.activeFocusItem && win.activeFocusItem!==grid) win.activeFocusItem.focus=false
                forceActiveFocus()
                if(Math.abs(destination-(gridScroll.running ? gridScroll.to : contentY))>.5) { gridScroll.to=destination;gridScroll.restart() }
                if(previousIndex!==currentIndex) backend.navigationMoved()
            }
            NumberAnimation { id: gridScroll; target: grid; property: "contentY"; duration: Theme.motion ? 75 : 0; easing.type: Easing.OutCubic }
            Keys.onPressed: function(event) {
                var commands={};commands[Qt.Key_Left]="left";commands[Qt.Key_Right]="right";commands[Qt.Key_Up]="up";commands[Qt.Key_Down]="down";commands[Qt.Key_Return]="activate";commands[Qt.Key_Enter]="activate";commands[Qt.Key_Escape]="back"
                if(commands[event.key]) event.accepted=win.controllerInput(commands[event.key])
            }
            visible: !homeVisible && libraryDesign==="classic"
            onVisibleChanged: if(!visible) gridScroll.stop()
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            property int layoutColumns: Math.max(1, Math.min(Math.max(1,Math.floor(width / (160 + gridGap))), columnCount > 0 ? columnCount : Math.round(width / (coverSize + gridGap))))
            readonly property int effectiveColumns: Math.max(1,Math.floor((width+.001)/cellWidth))
            cellWidth: Math.floor(width / layoutColumns)
            property real cardWidth: cellWidth - gridGap
            cellHeight: cardWidth * Theme.coverAspect + Theme.cardFooterHeight + gridGap
            model: libraryModel
            cacheBuffer: cellHeight*2
            reuseItems: true
            flickDeceleration: 2200
            maximumFlickVelocity: 3500
            ScrollBar.vertical: ScrollBar { }
            delegate: Item {
                id: gridDelegate
                required property var record
                required property int index
                property int libraryIndex: index
                property var modelData: record
                width: grid.cellWidth; height: grid.cellHeight
                Loader {
                    active: grid.visible
                    asynchronous: !grid.activeFocus || gridDelegate.index!==grid.currentIndex
                    Rectangle { anchors.fill: parent;radius: Theme.radius;color: Theme.surface;visible: parent.status!==Loader.Ready }
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: grid.cardWidth; height: grid.cellHeight-gridGap
                    sourceComponent: Component { GameCard {
                        width: grid.cardWidth; height: grid.cellHeight-gridGap
                        game: gridDelegate.modelData; scrolling: grid.moving || gridScroll.running
                        selected: grid.activeFocus && gridDelegate.index===grid.currentIndex
                        transferState: backend.transferStates[gridDelegate.modelData.id] || "idle"
                        onLaunchRequested: win.launchGame(gridDelegate.modelData)
                        onSettingsRequested: win.openGame(gridDelegate.modelData)
                        onCloudRequested: { selectGame(gridDelegate.modelData); historyTabs.currentIndex=0; backend.history(activeId); historyDialog.open() }
                        onRemoveRequested: { selectGame(gridDelegate.modelData); deleteDialog.open() }
                        onFavoriteRequested: backend.toggleFavorite(gridDelegate.modelData.id)
                    } }
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
            AppBusyIndicator { running: backend.busy; visible: running; implicitWidth: 24; implicitHeight: 24 }
            ProgressBar { visible: backend.matching; Layout.preferredWidth: 140; indeterminate: backend.matching && backend.matchProgress.done===0; from: 0; to: Math.max(1,backend.matchProgress.total); value: backend.matchProgress.done }
            Label { visible: backend.matching; text: backend.matchProgress.done+" / "+backend.matchProgress.total; font.pixelSize: 12; color: Theme.secondary }
            AppButton { visible: backend.matching; text: backend.matchProgress.cancelled ? "正在停止" : "停止查找"; enabled: !backend.matchProgress.cancelled; onClicked: backend.cancelMatching() }
            Rectangle { visible: !backend.busy; width: 6; height: 6; radius: 3; color: Theme.accent }
            Label { text: backend.status; color: Theme.secondary; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight; ToolTip.visible: !backend.controllerMode && statusHover.hovered; ToolTip.text: text; HoverHandler { id: statusHover } }
            Label { objectName: "watchStatus"; visible: backend.settings.watch; text: backend.watchInfo.message; color: backend.watchInfo.failed ? Theme.accent : Theme.secondary; font.pixelSize: 11; Layout.minimumWidth: 0; Layout.maximumWidth: win.width<1100 ? 130 : 300; elide: Text.ElideRight; ToolTip.visible: !backend.controllerMode && watchStatusHover.hovered; ToolTip.text: text+"\n点击调整自动备份、上传和保留份数"; HoverHandler { id: watchStatusHover; cursorShape: Qt.PointingHandCursor } TapHandler { onTapped: win.openSettingsPage(1) } }
            AppButton { visible: backend.watchInfo.failed>0; text: "重试自动备份/上传"; enabled: backend.settings.watch && !backend.watchInfo.working; onClicked: backend.retryAutoBackups() }
            Label { visible: backend.gamepadConnected; text: (win.libraryDesign==="atlas" ? "右摇杆 缩放  " : backend.settings.controller_tilt!==false ? "右摇杆 倾斜  " : "")+"A 启动  B 返回  X 收藏  Y 存档  View 搜索／返回  Menu 游戏选项"; color: Theme.secondary; font.pixelSize: 11;Layout.maximumWidth: Math.max(180,win.width*.47);elide: Text.ElideRight;ToolTip.visible: !backend.controllerMode && hintHover.hovered;ToolTip.text: text;HoverHandler { id: hintHover } }
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
        onRejected: restoreLayout()
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
                Switch { id: recommendationsToggle; objectName: "recommendationsToggle"; text: "首页游戏推荐" }
                RowLayout {
                    CheckBox { id: steamRecommendations; text: "Steam（国区）"; enabled: recommendationsToggle.checked }
                    CheckBox { id: xboxRecommendations; text: "Xbox（港区）"; enabled: recommendationsToggle.checked }
                }
                Label { text: backend.recommendations.status; visible: !!text; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
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
                Switch { id: watchSwitch; text: "游戏退出后自动备份一次" }
                CheckBox { id: traySwitch; text: "关闭主窗口时留在托盘"; checked: backend.settings.close_to_tray }
                RowLayout { Label { text: "监听间隔（秒）"; Layout.fillWidth: true } CompactSpinBox { id: watchInterval; from: 2; to: 60; stepSize: 1; value: backend.settings.watch_interval } }
                RowLayout { Label { text: "每款游戏本机自动备份保留份数"; Layout.fillWidth: true } CompactSpinBox { id: autoKeep; objectName: "autoSnapshotKeep"; from: 1; to: 100; value: backend.settings.auto_snapshot_keep || 5 } }
                CheckBox { id: autoUpload; text: "自动备份后上传云端"; enabled: watchSwitch.checked }
                Label { text: "仅清理本机自动备份，手动备份和云端存档保留。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                AppButton { text: "设置云端连接与备份文件夹"; Layout.fillWidth: true; onClicked: win.openCloud() }
                Label { text: backend.settings.cloud_folder ? "云端文件夹："+backend.settings.cloud_folder : "尚未设置云端，可先使用本地备份。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                }
                ColumnLayout {
                visible: settingsTabs.currentIndex===2; Layout.fillWidth: true; spacing: 12
                Label { text: "游戏库主页"; font.pixelSize: 16; font.weight: Font.DemiBold }
                RowLayout { Label { text: "封面大小"; Layout.fillWidth: true } CompactSpinBox { objectName: "homeCoverSize"; from: 120; to: 280; stepSize: 8; value: homeCoverSize; onValueModified: homeCoverSize=value } }
                RowLayout { Label { text: "封面间距"; Layout.fillWidth: true } CompactSpinBox { objectName: "homeGap"; from: 8; to: 32; stepSize: 2; value: homeGap; onValueModified: homeGap=value } }
                CheckBox { objectName: "homePreviewToggle"; text: "最近游戏大预览"; checked: homeRecentPreview; onToggled: homeRecentPreview=checked }
                Label { text: "内页游戏列表"; font.pixelSize: 16; font.weight: Font.DemiBold }
                RowLayout { Label { text: "封面大小"; Layout.fillWidth: true } NodeSlider { objectName: "coverSlider"; value: coverSize; Layout.preferredWidth: 260; onMoved: { coverSize=Math.round(value); columnCount=0 } } }
                RowLayout { Label { text: "每行游戏数（0 为自动）"; Layout.fillWidth: true } CompactSpinBox { from: 0; to: 10; value: columnCount; onValueModified: columnCount=value } }
                RowLayout { Label { text: "卡片间距"; Layout.fillWidth: true } CompactSpinBox { from: 8; to: 48; stepSize: 2; value: gridGap; onValueModified: gridGap=value } }
                CheckBox { text: "仅显示已安装游戏"; checked: installedOnly; onToggled: installedOnly=checked }
                AppButton { text: "恢复默认布局"; onClicked: { coverSize=210; columnCount=0; gridGap=22; installedOnly=false;homeCoverSize=176;homeGap=14;homeRecentPreview=true } }
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
            onRejected: { restoreLayout();settingsDialog.close() }
            onAccepted: {
                backend.saveSettings({playnite:playnitePath.text, library:libraryPath.text, snapshots:snapshotPath.text, watch:watchSwitch.checked,watch_upload:autoUpload.checked,close_to_tray:traySwitch.checked,watch_interval:watchInterval.value,auto_snapshot_keep:autoKeep.value,recommendations_enabled:recommendationsToggle.checked,recommendations_steam:steamRecommendations.checked,recommendations_xbox:xboxRecommendations.checked}); saveLayout(); settingsDialog.close()
            }
        }
    }

    Dialog {
        id: recommendationDialog; objectName: "recommendationDialog"
        anchors.centerIn: parent; width: Math.min(win.width-48,1260); height: win.height-64; modal: true
        title: "游戏推荐"
        onOpened: { backend.recommendations.start();Qt.callLater(function() { if(recommendationLoader.item) recommendationLoader.item.focusFirst() }) }
        function controllerInput(command) {
            if(command==="back") { close();return true }
            var home=recommendationLoader.item;if(!home) return true
            if(command==="activate") { home.activateSelected();return true }
            if(["up","down","left","right"].indexOf(command)>=0) home.navigateFocus(command)
            if(command==="next" || command==="previous") { var shelf=home.currentShelf();if(shelf) shelf.pageSelection(command==="next" ? 1 : -1) }
            return true
        }
        contentItem: Loader {
            id: recommendationLoader; active: recommendationDialog.visible
            onLoaded: Qt.callLater(function() { if(item) item.focusFirst() })
            sourceComponent: Component { LibraryHome { listObjectName: "recommendationHomeList"; sections: backend.recommendations.sections; coverSize: win.homeCoverSize; cardGap: win.homeGap; recentPreview: false } }
        }
        footer: DialogButtonBox {
            AppButton { text: "关闭"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
            onRejected: recommendationDialog.close()
        }
    }

    GameSettingsDialog {
        id: gameDialog; anchors.centerIn: parent
        onClosed: Qt.callLater(function() { if(!backend.popupActive()) win.focusContent() })
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
        property string controllerZone: "actions"
        property int controllerAction: 0
        property bool loadPending: false
        readonly property var actionControls: [historyLocal,historyUpload,historyRetry,historyRefresh]
        function loadTab() { loadPending=backend.busy;if(!loadPending) { if(historyTabs.currentIndex===0) backend.history(activeId);else backend.refreshCloudHistory(activeId) } }
        function changeTab(value) { historyTabs.currentIndex=Math.max(0,Math.min(1,value));historyList.currentIndex=0;controllerZone="tabs";loadTab() }
        Connections { target: backend;function onChanged() { if(historyDialog.visible && historyDialog.loadPending && !backend.busy) historyDialog.loadTab() } }
        function restoreSelected() { if(backend.busy || !historyList.count) return;var row=historyList.model[historyList.currentIndex];if(row) restoreDialog.begin(activeId,row.id || 0,historyTabs.currentIndex===1 ? row : ({})) }
        function controllerInput(command) {
            if(command==="back") { close();return true }
            if(command==="previous" || command==="next") { changeTab(historyTabs.currentIndex+(command==="previous" ? -1 : 1));return true }
            if(command==="favorite") { if(historyRefresh.enabled) historyRefresh.clicked();return true }
            if(command==="activate") {
                if(controllerZone==="actions") { var action=actionControls[controllerAction];if(action.enabled) action.clicked() }
                else if(controllerZone==="tabs") { if(historyList.count) { controllerZone="records";historyList.currentIndex=Math.max(0,historyList.currentIndex) } }
                else restoreSelected()
                return true
            }
            if(command==="left" || command==="right") {
                if(controllerZone==="actions") controllerAction=Math.max(0,Math.min(3,controllerAction+(command==="left" ? -1 : 1)))
                else if(controllerZone==="tabs") changeTab(historyTabs.currentIndex+(command==="left" ? -1 : 1))
            } else if(command==="up" || command==="down") {
                if(controllerZone==="actions" && command==="down") controllerZone="tabs"
                else if(controllerZone==="tabs") { if(command==="up") controllerZone="actions";else if(historyList.count) { controllerZone="records";historyList.currentIndex=Math.max(0,historyList.currentIndex) } }
                else if(controllerZone==="records") { if(command==="up" && historyList.currentIndex<=0) controllerZone="tabs";else { historyList.currentIndex=Math.max(0,Math.min(historyList.count-1,historyList.currentIndex+(command==="up" ? -1 : 1)));historyList.positionViewAtIndex(historyList.currentIndex,ListView.Contain) } }
            }
            return true
        }
        onAboutToShow: { controllerZone="actions";controllerAction=0;historyList.currentIndex=historyList.count ? 0 : -1 }
        onClosed: { loadPending=false;Qt.callLater(function() { if(!backend.popupActive()) win.focusContent() }) }
        exit: Transition {}
        Overlay.modal: Rectangle { color: "#bb000000" }
        contentItem: ColumnLayout {
            RowLayout {
                IconButton { iconName: "cloud"; transferState: backend.transferStates[activeId] || "idle"; hoverEnabled: false; focusPolicy: Qt.NoFocus }
                Label { text: (backend.transferStates[activeId] || "idle")==="saving" ? "正在保存本地备份…" : backend.transferStates[activeId]==="uploading" ? "本地已保存，正在上传…" : backend.transferStates[activeId]==="success" ? "云端上传成功" : backend.transferStates[activeId]==="failed" ? "上传失败，本地备份保留，可补传" : "本地备份完成后再上传"; Layout.fillWidth: true; color: Theme.secondary }
            }
            RowLayout {
                enabled: !backend.busy
                AppButton { id: historyLocal;objectName: "historyLocalBackup";text: "本地备份";highlighted: backend.controllerMode && historyDialog.controllerZone==="actions" && historyDialog.controllerAction===0;enabled: !!backend.libraryGame(activeId).saveSet;onClicked: backend.localSave(activeId) }
                AppButton { id: historyUpload;objectName: "historyUploadBackup";text: "备份并上传";highlighted: backend.controllerMode && historyDialog.controllerZone==="actions" && historyDialog.controllerAction===1;enabled: !!backend.libraryGame(activeId).saveSet && !!backend.settings.cloud_folder;onClicked: backend.cloudSave(activeId) }
                AppButton { id: historyRetry;text: "重试上传";highlighted: backend.controllerMode && historyDialog.controllerZone==="actions" && historyDialog.controllerAction===2;enabled: !!backend.settings.cloud_folder;onClicked: backend.retry(activeId) }
                AppButton { id: historyRefresh;text: "刷新记录";highlighted: backend.controllerMode && historyDialog.controllerZone==="actions" && historyDialog.controllerAction===3;onClicked: { if(historyTabs.currentIndex===0) backend.history(activeId); else backend.refreshCloudHistory(activeId) } }
            }
            TabBar { id: historyTabs; objectName: "historyTabs"; Layout.fillWidth: true; TabButton { text: "本机版本" } TabButton { text: "云端 / 其他设备" } }
            Label { text: historyTabs.currentIndex===0 ? "按时间从新到旧排列，恢复前先备份当前存档。" : "点击刷新读取云端版本；选择恢复时下载并校验，不自动覆盖本机。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            ListView {
                id: historyList;objectName: "historyList";currentIndex: -1;highlightFollowsCurrentItem: false
                Layout.fillWidth: true; Layout.fillHeight: true; model: historyTabs.currentIndex===0 ? backend.snapshots : backend.cloudSnapshots; clip: true
                delegate: ItemDelegate {
                    required property var modelData
                    required property int index
                    highlighted: backend.controllerMode && historyDialog.controllerZone==="records" && historyList.currentIndex===index
                    background: Rectangle { color: parent.highlighted ? Theme.selection : "transparent";radius: Theme.radius;border.color: parent.highlighted ? Theme.accent : "transparent";border.width: 2 }
                    onClicked: { historyList.currentIndex=index;historyDialog.controllerZone="records" }
                    width: ListView.view.width; height: 84
                    contentItem: RowLayout {
                        ColumnLayout {
                            Layout.fillWidth: true
                            Label { objectName: "snapshotTime"; text: backend.formatLocalTime(modelData.created_at || ""); Layout.fillWidth: true; elide: Text.ElideRight }
                            Label { text: (historyTabs.currentIndex===0 ? (modelData.event==="game_stop" || modelData.event==="game_start" ? "自动备份 · " : modelData.event==="manual" ? "手动备份 · " : "")+(modelData.uploaded ? "已上传" : "仅本地") : (modelData.computer || "云端版本")) + "  ·  " + (modelData.note || "无备注"); Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary; font.pixelSize: 12 }
                        }
                        AppButton { text: "备注"; visible: historyTabs.currentIndex===0; enabled: !backend.busy; onClicked: { noteDialog.snapshotId=modelData.id; snapshotNote.text=modelData.note || ""; noteDialog.open() } }
                        AppButton { text: historyTabs.currentIndex===0 ? "恢复" : "下载并恢复"; enabled: !backend.busy; onClicked: restoreDialog.begin(activeId,modelData.id || 0,historyTabs.currentIndex===1 ? modelData : ({})) }
                    }
                }
                ScrollBar.vertical: ScrollBar {}
                Label { visible: parent.count===0; anchors.centerIn: parent; text: historyTabs.currentIndex===0 ? "暂无本机记录，先创建一份备份。" : "点击刷新记录，查看云端版本。"; color: Theme.secondary }
            }
            Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
            Label { text: "上 / 下 切换操作与备份 · A 确认 / 预览恢复 · LB / RB 本地 / 云端 · B 返回";visible: backend.controllerMode;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary }
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
    RestoreDialog { id: restoreDialog; anchors.centerIn: parent }
}
