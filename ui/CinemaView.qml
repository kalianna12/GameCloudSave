import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Item {
    id: cinema
    property var games: []
    property var game: ({})
    property var media: ({})
    property bool controllerFocused: false
    property bool launching: false
    property bool playing: false
    property bool muted: true
    property bool videoFailed: false
    readonly property bool compact: height<470
    readonly property int selectedIndex: games.findIndex(function(g) { return g.id===game.id })
    readonly property bool canPlay: !!media.videoUrl && !launching && visible && !!Window.window && Window.window.visible && Window.window.active && backend.watchInfo.running===0
    signal selected(string ident)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    signal removeRequested(var game)
    function syncVideo() {
        if(playing && canPlay) video.active=true
        else { if(video.item) video.item.stop();video.active=false }
    }
    onPlayingChanged: syncVideo()
    function navigate(direction) {
        if(direction==="up" || direction==="left" && selectedIndex<=0) return false
        if(direction==="left" || direction==="right") move(direction==="left" ? -1 : 1)
        return true
    }
    function move(step) { if(games.length) selected(games[Math.max(0,Math.min(games.length-1,selectedIndex+step))].id) }
    function page(step) { move(step*Math.max(1,Math.floor(film.width/124))) }
    function reveal() { film.positionViewAtIndex(Math.max(0,selectedIndex),ListView.Contain) }
    onGameChanged: { playing=false;videoFailed=false;Qt.callLater(function() { film.positionViewAtIndex(Math.max(0,selectedIndex),ListView.Contain) });if(Theme.motion) reveal.restart() }
    onMediaChanged: { playing=false;videoFailed=false }
    onCanPlayChanged: { if(!canPlay) playing=false;syncVideo() }
    onVisibleChanged: if(!visible) playing=false
    Rectangle { anchors.fill: parent; color: "#100e14"; radius: 8 }
    Image {
        id: backdrop; anchors.fill: parent
        source: cinema.game.backgroundUrl || cinema.media.backgroundUrl || ""; asynchronous: true; cache: true
        fillMode: Image.PreserveAspectCrop; sourceSize.width: 1600; opacity: .8
    }
    NumberAnimation { id: reveal; target: backdrop; property: "opacity"; from: .3; to: .8; duration: 240 }
    Image {
        visible: !backdrop.source.toString() || backdrop.status===Image.Error
        anchors { top: parent.top; bottom: filmBand.top; right: parent.right; rightMargin: 30; topMargin: 24; bottomMargin: 24 }
        width: Math.min(parent.width*.44,height/.72); source: cinema.game.coverHighUrl || cinema.game.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectFit; sourceSize.width: 900
    }
    Loader {
        id: video; objectName: "cinemaVideoLoader"; anchors.fill: parent; active: false
        source: "CinemaVideo.qml"
        onLoaded: { item.source=cinema.media.videoUrl;item.muted=cinema.muted }
        onStatusChanged: if(status===Loader.Error) { cinema.videoFailed=true;cinema.playing=false }
        Connections { target: video.item; ignoreUnknownSignals: true; function onPlaybackFailed() { cinema.videoFailed=true;cinema.playing=false } function onFinished() { cinema.playing=false } }
    }
    Rectangle { anchors.fill: parent; opacity: cinema.playing ? .35 : 1; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#f5100e14" } GradientStop { position: .4; color: "#d0100e14" } GradientStop { position: .82; color: "#10100e14" } GradientStop { position: 1; color: "#40100e14" } } }
    Rectangle { anchors.fill: parent; gradient: Gradient { GradientStop { position: 0; color: "#10100e14" } GradientStop { position: .55; color: "#00100e14" } GradientStop { position: 1; color: "#ff100e14" } } }
    ColumnLayout {
        objectName: "cinemaInformation"
        x: cinema.width<900 ? 24 : 42; y: Math.max(12,(filmBand.y-height)*.5); width: Math.min(cinema.width*.58,620); spacing: cinema.compact ? 8 : 16
        Label { text: cinema.game.name || "没有匹配的游戏"; Layout.fillWidth: true; font.pixelSize: Math.max(24,Math.min(cinema.compact ? 30 : 46,cinema.width*.038)); font.weight: Font.DemiBold; wrapMode: Text.Wrap; maximumLineCount: cinema.compact ? 2 : 3; elide: Text.ElideRight; color: "#fff8ef" }
        Label { visible: !!cinema.game.series && !cinema.compact; text: cinema.game.series || ""; color: "#e4c7aa"; font.pixelSize: 15; Layout.fillWidth: true; elide: Text.ElideRight }
        Label { text: [cinema.game.category,cinema.game.release_date].filter(Boolean).join("  /  "); visible: !!cinema.game.id; color: "#c9c0d1"; font.pixelSize: 13 }
        Flow {
            visible: !cinema.compact
            Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: 10
            Repeater { model: (cinema.game.tags || []).filter(function(t) { return t!==cinema.game.category }).slice(0,4); Label { required property string modelData; text: modelData; color: "#dfd3e8"; font.pixelSize: 12 } }
        }
        GameActions {
            game: cinema.game; light: true; Layout.preferredWidth: Math.min(300,parent.width); Layout.preferredHeight: cinema.compact ? 38 : 46
            onLaunchRequested: function(game) { cinema.launchRequested(game) }
            onDetailsRequested: function(game) { cinema.detailsRequested(game) }
            onCloudRequested: function(game) { cinema.cloudRequested(game) }
            onRemoveRequested: function(game) { cinema.removeRequested(game) }
        }
        RowLayout {
            visible: !!cinema.game.id; spacing: 14
            IconButton { iconName: "star"; bare: true; lightIcon: true; label: cinema.game.favorite ? "已收藏" : "收藏"; width: 88; hint: label; onClicked: backend.toggleFavorite(cinema.game.id) }
            AppButton { objectName: "cinemaVideoButton"; visible: !!cinema.media.videoUrl; enabled: cinema.canPlay; text: cinema.playing ? "停止预告" : "播放预告"; flat: true; onClicked: cinema.playing=!cinema.playing }
            AppButton { visible: cinema.playing; text: cinema.muted ? "开启声音" : "静音"; flat: true; onClicked: { cinema.muted=!cinema.muted;if(video.item) video.item.muted=cinema.muted } }
            AppButton { visible: !cinema.compact || !cinema.playing; text: backend.mediaLoading ? "正在读取媒体" : "更新媒体"; enabled: !backend.mediaLoading; flat: true; onClicked: backend.loadLibraryMedia(true) }
        }
        Label { visible: cinema.videoFailed; text: "预告片无法播放，可更新媒体后重试"; color: "#e4c7aa"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
    }
    Item {
        id: filmBand; objectName: "cinemaFilmBand"; x: 0; width: parent.width; height: Math.min(170,Math.max(120,cinema.height*.3)); anchors.bottom: parent.bottom
        Rectangle { anchors.fill: parent; color: "#80100e14" }
        Repeater { model: Math.ceil(filmBand.width/20); Rectangle { required property int index; x: index*20+5; y: 6; width: 8; height: 5; radius: 1; color: "#65516c" } }
        ListView {
            id: film; objectName: "cinemaFilmstrip"; x: 18; y: 24; width: parent.width-36; height: parent.height-48
            model: cinema.games; orientation: ListView.Horizontal; spacing: 12; clip: true; reuseItems: true; cacheBuffer: 240
            delegate: Item {
                required property var modelData; required property int index
                width: 112; height: film.height
                Rectangle {
                    width: parent.width; height: parent.height-24; radius: 3; color: "#28212d"; border.color: modelData.id===cinema.game.id ? Theme.accent : "#55465c"; border.width: modelData.id===cinema.game.id ? 3 : 1
                    Image { anchors.fill: parent; anchors.margins: 4; source: modelData.backgroundUrl || modelData.coverUrl || ""; fillMode: Image.PreserveAspectFit; asynchronous: true; sourceSize.width: 240 }
                    HoverHandler { id: filmHover; enabled: !backend.controllerMode }
                    TapHandler { onTapped: cinema.selected(modelData.id);onDoubleTapped: cinema.detailsRequested(modelData) }
                    scale: filmHover.hovered && Theme.motion ? .96 : 1
                    Behavior on scale { NumberAnimation { duration: Theme.motion ? 120 : 0 } }
                }
                Label { width: parent.width; y: parent.height-18; text: modelData.name; color: modelData.id===cinema.game.id ? "#fff8ef" : "#b3a2bc"; elide: Text.ElideRight; font.pixelSize: 11; ToolTip.visible: nameHover.hovered && !backend.controllerMode; ToolTip.text: text; ToolTip.delay: 650; HoverHandler { id: nameHover; enabled: !backend.controllerMode } }
            }
            WheelHandler { target: null; onWheel: function(event) { film.contentX=Math.max(0,Math.min(film.contentWidth-film.width,film.contentX-(event.angleDelta.x || event.angleDelta.y)));event.accepted=true } }
        }
        Repeater { model: Math.ceil(filmBand.width/20); Rectangle { required property int index; x: index*20+5; y: filmBand.height-10; width: 8; height: 5; radius: 1; color: "#65516c" } }
    }
    IconButton { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 14; iconName: "arrow-right"; lightIcon: true; bare: true; hint: "下一款游戏"; enabled: cinema.selectedIndex<cinema.games.length-1; onClicked: cinema.move(1) }
}
