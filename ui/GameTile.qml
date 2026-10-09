import QtQuick
import QtQuick.Window
import QtQuick.Controls
Item {
    id: tile
    readonly property bool libraryTile: true
    property var game: ({})
    property bool featured: false
    property bool scrolling: false
    property bool selected: false
    property bool selectOnly: false
    property string lastGameId: ""
    signal selectionRequested()
    signal focusRequested()
    onGameChanged: { if(featured && Theme.motion && !scrolling && game.id!==lastGameId) reveal.restart();lastGameId=game.id || "" }
    NumberAnimation { id: reveal; target: poster; property: "opacity"; from: .55; to: 1; duration: 140 }
    activeFocusOnTab: !featured
    onActiveFocusChanged: if(activeFocus && !featured) focusRequested()
    Keys.onReturnPressed: detailsRequested(game)
    signal detailsRequested(var game)
    signal launchRequested(var game)
    signal cloudRequested(var game)
    property string platformName: game.platform==="steam" ? "Steam" : game.platform==="epic" ? "Epic" : game.platform==="ubisoft" ? "Ubisoft" : "本地"
    HoverHandler { id: hover; enabled: !backend.controllerMode }
    Rectangle {
        id: poster; width: parent.width; height: parent.height-48; radius: 6; color: Theme.surface; clip: true
        Image {
            id: cover; anchors.fill: parent
            source: tile.featured && tile.game.backgroundUrl ? tile.game.backgroundUrl : tile.game.coverHighUrl || tile.game.coverUrl || ""
            asynchronous: true; cache: true; fillMode: Image.PreserveAspectCrop
            sourceSize: Qt.size(tile.featured ? Math.min(1440,Math.ceil(tile.width*Screen.devicePixelRatio)) : Math.min(720,Math.ceil(tile.width*Screen.devicePixelRatio)),0)
        }
        Label { visible: !cover.source.toString() || cover.status===Image.Error; anchors.centerIn: parent; width: parent.width-20; text: tile.game.name || ""; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; color: Theme.secondary }
        Rectangle { objectName: "tileFocusRing"; readonly property real focusWidth: border.width; anchors.fill: parent; color: "transparent"; radius: 6; border.width: tile.selected ? 3 : hover.hovered && !tile.scrolling && !tile.featured ? 2 : 0; border.color: tile.selected ? Theme.accent : Theme.secondary; Behavior on border.width { NumberAnimation { duration: Theme.motion ? 100 : 0 } } }
        TapHandler { onTapped: { tile.forceActiveFocus();if(tile.selectOnly) tile.selectionRequested();else tile.detailsRequested(tile.game) } }
        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 48
            color: Theme.surface; opacity: tile.featured || hover.hovered && !tile.scrolling || tile.activeFocus ? .95 : 0
            enabled: opacity>.5
            Behavior on opacity { NumberAnimation { duration: Theme.motion && !tile.scrolling ? 120 : 0 } }
            Row {
                anchors.centerIn: parent; spacing: 8
                IconButton { iconName: "play"; accent: true; hint: "启动"; enabled: !backend.busy; onClicked: tile.launchRequested(tile.game) }
                IconButton { iconName: "settings"; hint: "设置"; enabled: !backend.busy; onClicked: tile.detailsRequested(tile.game) }
                IconButton { iconName: "cloud"; hint: "存档记录"; enabled: !backend.busy; onClicked: tile.cloudRequested(tile.game) }
            }
        }
    }
    Column {
        anchors { left: parent.left; right: parent.right; top: poster.bottom; topMargin: 8 }
        spacing: 4
        Label { width: parent.width; text: tile.game.name || ""; font.pixelSize: tile.featured ? 16 : 13; font.bold: true; color: Theme.text; elide: Text.ElideRight }
        Label { width: parent.width; text: tile.platformName+(tile.game.import_source==="playnite" ? " · Playnite" : "")+(tile.game.installed ? " · 已安装" : ""); color: Theme.secondary; font.pixelSize: 11; elide: Text.ElideRight }
    }
    ToolTip.visible: hover.hovered && !scrolling; ToolTip.delay: 900; ToolTip.text: game.name || ""
}
