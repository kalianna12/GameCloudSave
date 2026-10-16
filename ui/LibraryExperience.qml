import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ExperienceData.js" as Data
FocusScope {
    id: experience
    property string design: "shelf"
    property var games: []
    property int coverSize: 176
    property bool launching: false
    property string groupMode: backend.settings.experience_group || "category"
    property string groupValue: ""
    property string selectedId: ""
    property var groups: Data.groupGames(games,groupMode)
    property var filteredGames: !groupValue ? games : ((groups.find(function(g) { return g.name===groupValue }) || {}).items || [])
    readonly property var visibleGroups: groupValue ? groups.filter(function(g) { return g.name===groupValue }) : groups
    readonly property var selectedGame: filteredGames.find(function(g) { return g.id===selectedId }) || ({})
    readonly property var media: backend.libraryMedia[selectedId] || ({})
    readonly property bool contentFocused: !!Window.window && Window.window.activeFocusItem===experience
    readonly property var toolbarControls: [grouping,groupChoice,arrangement,atlasOrder,randomScope,dice]
    property var randomBag: []
    property string randomMessage: ""
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal removeRequested(var game)
    signal boundaryRequested(string direction)
    function focusContent() { var item=Window.window ? Window.window.activeFocusItem : null;if(item && item!==experience) item.focus=false;experience.forceActiveFocus() }
    function choose(ident) { if(selectedId!==ident) backend.navigationMoved();selectedId=ident;focusContent() }
    function focusFirst() {
        if(scene.item && scene.item.resetPosition) scene.item.resetPosition()
        var first=design==="atlas" && scene.item && scene.item.firstGame ? scene.item.firstGame() : filteredGames[0]
        if(first) choose(first.id);else focusContent()
        Qt.callLater(function() { if(scene.item && scene.item.reveal) scene.item.reveal() })
    }
    function ensureSelection() { if(!filteredGames.some(function(g) { return g.id===selectedId })) selectedId=filteredGames.length ? filteredGames[0].id : "";randomBag=[];randomMessage="" }
    onFilteredGamesChanged: ensureSelection()
    onDesignChanged: { groupValue="";ensureSelection();if(design==="cinema") backend.loadLibraryMedia() }
    Component.onCompleted: { ensureSelection();if(design==="cinema") backend.loadLibraryMedia() }
    Connections { target: backend; function onGamesChanged() { if(experience.design==="cinema") backend.loadLibraryMedia() } function onSettingsChanged() { if(experience.design==="cinema") backend.loadLibraryMedia() } }
    onGroupModeChanged: { groupValue="";randomBag=[];if(grouping) grouping.currentIndex=["category","series","tags","year","all"].indexOf(groupMode) }
    onGroupValueChanged: if(groupChoice) groupChoice.currentIndex=Math.max(0,groupChoice.model.indexOf(groupValue))
    onGroupsChanged: { if(groupValue && !groups.some(function(g) { return g.name===groupValue })) groupValue="" }
    function randomGame() {
        var pool=filteredGames.filter(function(g) { return randomScope.currentIndex!==1 || g.installed }).filter(function(g) { return randomScope.currentIndex!==2 || !g.last_played })
        if(!pool.length) { randomMessage="当前范围没有游戏";return }
        var allowed=Object.create(null);pool.forEach(function(g) { allowed[g.id]=true })
        randomBag=randomBag.filter(function(id) { return allowed[id] })
        if(!randomBag.length) {
            randomBag=pool.map(function(g) { return g.id })
            for(var i=randomBag.length-1;i>0;i--) { var j=Math.floor(Math.random()*(i+1)),v=randomBag[i];randomBag[i]=randomBag[j];randomBag[j]=v }
            if(randomBag.length>1 && randomBag[randomBag.length-1]===selectedId) { var first=randomBag[0];randomBag[0]=randomBag[randomBag.length-1];randomBag[randomBag.length-1]=first }
        }
        var next=randomBag[randomBag.length-1];randomBag=randomBag.slice(0,-1);choose(next);randomMessage=""
        Qt.callLater(function() { if(scene.item && scene.item.celebrate) scene.item.celebrate() })
    }
    function controllerInput(command) {
        var controls=toolbarControls.filter(function(c) { return c.visible && c.enabled }),focus=Window.window ? Window.window.activeFocusItem : null,index=-1
        while(focus) { if(index<0) index=controls.indexOf(focus);focus=focus.parent }
        if(index>=0) {
            if(command==="down") focusContent()
            else if(command==="up") boundaryRequested("up")
            else if(command==="left" || command==="right") { var n=index+(command==="left" ? -1 : 1);if(n<0) boundaryRequested("left");else controls[Math.min(controls.length-1,n)].forceActiveFocus() }
            else if(command==="activate" && controls[index]===dice) { dice.animateRoll();randomGame() }
            return true
        }
        if(command==="next" || command==="previous") { if(scene.item) scene.item.page(command==="next" ? 1 : -1);return true }
        if(["left","right","up","down"].indexOf(command)>=0) {
            focusContent()
            if(scene.item && !scene.item.navigate(command)) {
                if(command==="up") grouping.forceActiveFocus()
                else if(command==="left") boundaryRequested("left")
            }
            return true
        }
        if(!selectedGame.id) return true
        if(command==="favorite") backend.toggleFavorite(selectedId)
        else if(command==="launch") launchRequested(selectedGame)
        else if(command==="activate" || command==="history") detailsRequested(selectedGame)
        return true
    }
    Keys.onPressed: function(event) {
        var keys={};keys[Qt.Key_Left]="left";keys[Qt.Key_Right]="right";keys[Qt.Key_Up]="up";keys[Qt.Key_Down]="down";keys[Qt.Key_Return]="activate";keys[Qt.Key_Enter]="activate"
        if(keys[event.key]) { controllerInput(keys[event.key]);event.accepted=true }
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 12
        Flow {
            Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: 8
            AppComboBox { id: grouping; objectName: "experienceGrouping"; width: 135; model: ["按类别分组","按系列分组","按标签分组","按发行年份","不分组"]; currentIndex: ["category","series","tags","year","all"].indexOf(experience.groupMode); onActivated: { experience.groupMode=["category","series","tags","year","all"][currentIndex];backend.saveSettings({experience_group:experience.groupMode}) } }
            AppComboBox { id: groupChoice; objectName: "experienceGroupChoice"; width: 155; visible: experience.groupMode!=="all"; model: ["全部分组"].concat(experience.groups.map(function(g) { return g.name })); currentIndex: Math.max(0,model.indexOf(experience.groupValue)); onActivated: experience.groupValue=currentIndex>0 ? currentText : "" }
            AppComboBox { id: arrangement; objectName: "shelfArrangement"; width: 125; visible: experience.design==="shelf"; model: ["封面朝外","书脊排列"]; currentIndex: backend.settings.shelf_arrangement==="books" ? 1 : 0; onActivated: backend.saveSettings({shelf_arrangement:currentIndex===1 ? "books" : "covers"}) }
            AppComboBox { id: atlasOrder; objectName: "atlasOrder"; width: 175; visible: experience.design==="atlas"; model: ["发行：从早到晚","发行：从晚到早","名称排序"]; currentIndex: ["release_asc","release_desc","name"].indexOf(backend.settings.atlas_order || "release_asc"); onActivated: backend.saveSettings({atlas_order:["release_asc","release_desc","name"][currentIndex]}) }
            AppComboBox { id: randomScope; objectName: "randomScope"; width: 150; model: ["随机：当前范围","随机：已安装","随机：未启动"]; onActivated: experience.randomBag=[] }
            DiceButton { id: dice; objectName: "randomGame"; enabled: experience.filteredGames.length>0; onClicked: experience.randomGame() }
        }
        Label { visible: !!experience.randomMessage; text: experience.randomMessage; color: Theme.secondary; font.pixelSize: 12 }
        Loader {
            id: scene; objectName: "experienceScene"; Layout.fillWidth: true; Layout.fillHeight: true
            sourceComponent: experience.design==="shelf" ? shelves : experience.design==="cinema" ? cinema : atlas
            Component { id: shelves; ShelfView { objectName: "shelfExperience"; groups: experience.visibleGroups; selectedId: experience.selectedId; spines: backend.settings.shelf_arrangement==="books"; coverSize: experience.coverSize; controllerFocused: experience.contentFocused; onSelected: function(id) { experience.choose(id) } onDetailsRequested: function(game) { experience.detailsRequested(game) } } }
            Component { id: cinema; CinemaView { objectName: "cinemaExperience"; games: experience.filteredGames; game: experience.selectedGame; media: experience.media; categories: experience.groups; categoryValue: experience.groupValue; onCategorySelected: function(value) { experience.groupValue=value;experience.focusFirst() } controllerFocused: experience.contentFocused; launching: experience.launching; onSelected: function(id) { experience.choose(id) } } }
            Component { id: atlas; AtlasView { objectName: "atlasExperience"; games: experience.filteredGames; game: experience.selectedGame; groupMode: experience.groupMode; order: backend.settings.atlas_order || "release_asc"; controllerFocused: experience.contentFocused; launching: experience.launching; onSelected: function(id) { experience.choose(id) } } }
            Connections {
                target: scene.item; ignoreUnknownSignals: true
                function onDetailsRequested(game) { if(experience.design!=="shelf") experience.detailsRequested(game) }
                function onLaunchRequested(game) { experience.launchRequested(game) }
                function onCloudRequested(game) { experience.cloudRequested(game) }
                function onRemoveRequested(game) { experience.removeRequested(game) }
            }
        }
        RowLayout {
            visible: experience.design==="shelf"; Layout.fillWidth: true; Layout.minimumHeight: 58; spacing: 12
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Label { text: experience.selectedGame.name || "没有匹配的游戏"; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.text; font.pixelSize: 18; font.weight: Font.DemiBold }
                Label { text: [experience.selectedGame.series,experience.selectedGame.release_date].filter(Boolean).join("  /  "); visible: !!text; color: Theme.secondary; font.pixelSize: 12 }
            }
            IconButton { iconName: "star"; bare: true; hint: experience.selectedGame.favorite ? "取消收藏" : "收藏"; enabled: !!experience.selectedGame.id; onClicked: backend.toggleFavorite(experience.selectedId) }
            GameActions {
                Layout.preferredWidth: 230; Layout.preferredHeight: 42; game: experience.selectedGame
                onLaunchRequested: function(game) { experience.launchRequested(game) }
                onDetailsRequested: function(game) { experience.detailsRequested(game) }
                onCloudRequested: function(game) { experience.cloudRequested(game) }
                onRemoveRequested: function(game) { experience.removeRequested(game) }
            }
        }
    }
}
