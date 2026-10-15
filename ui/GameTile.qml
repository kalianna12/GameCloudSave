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
    HoverHandler { id: hover; enabled: !backend.controllerMode }
    Item {
        id: coverArea; width: parent.width; height: parent.height-(tile.featured ? 0 : 30)
        Rectangle {
            id: poster; objectName: "coverSurface"; anchors.fill: parent; radius: 10; color: Theme.surface; clip: true
            transform: [
                Rotation { objectName: "coverYaw"; origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 0; axis.y: 1; axis.z: 0; angle: coverEffect.yaw },
                Rotation { objectName: "coverPitch"; origin.x: poster.width/2; origin.y: poster.height/2; axis.x: 1; axis.y: 0; axis.z: 0; angle: coverEffect.pitch }
            ]
            Image {
                id: cover; anchors.fill: parent
                source: tile.featured && tile.game.backgroundUrl ? tile.game.backgroundUrl : tile.game.coverHighUrl || tile.game.coverUrl || ""
                asynchronous: true; cache: true; fillMode: Image.PreserveAspectCrop
                sourceSize: Qt.size(tile.featured ? Math.min(1440,Math.ceil(tile.width*Screen.devicePixelRatio)) : Math.min(720,Math.ceil(tile.width*Screen.devicePixelRatio)),0)
            }
            Label { visible: !cover.source.toString() || cover.status===Image.Error; anchors.centerIn: parent; width: parent.width-20; text: tile.game.name || ""; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter; color: Theme.secondary }
        }
        CoverEffects { id: coverEffect; anchors.fill: parent; surface: poster; identity: tile.game.id || ""; controllerFocused: tile.selected && backend.controllerMode; suspended: tile.scrolling; tiltLimit: tile.featured ? 7 : 18 }
        Rectangle { objectName: "tileFocusRing"; z: 10; readonly property real focusWidth: border.width; anchors.fill: parent; color: "transparent"; radius: 6; border.width: tile.selected ? 3 : hover.hovered && !tile.scrolling && !tile.featured ? 2 : 0; border.color: tile.selected ? Theme.accent : Theme.secondary; Behavior on border.width { NumberAnimation { duration: Theme.motion ? 100 : 0 } } }
        TapHandler { onTapped: { tile.forceActiveFocus();if(tile.selectOnly) tile.selectionRequested();else tile.detailsRequested(tile.game) } }
        Item {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: tile.featured ? 96 : 44; z: 6
            opacity: tile.featured || hover.hovered && !tile.scrolling || tile.activeFocus ? 1 : 0
            enabled: opacity>.5
            Behavior on opacity { NumberAnimation { duration: Theme.motion && !tile.scrolling ? 120 : 0 } }
            Rectangle { anchors.fill: parent; visible: tile.featured; gradient: Gradient { GradientStop { position: 0; color: "#00000000" } GradientStop { position: .36; color: "#aa000000" } GradientStop { position: 1; color: "#ed000000" } } }
            TitleLabel { objectName: "featuredGameTitle"; scrolling: tile.scrolling; visible: tile.featured; x: 16; y: 15; width: parent.width-32; text: tile.game.name || ""; font.pixelSize: 16; font.weight: Font.DemiBold; color: "white"; elide: Text.ElideRight; }
            Row {
                anchors.left: tile.featured ? parent.left : undefined; anchors.leftMargin: 16
                anchors.horizontalCenter: tile.featured ? undefined : parent.horizontalCenter
                anchors.bottom: parent.bottom; anchors.bottomMargin: tile.featured ? 12 : 1; spacing: 8
                IconButton { iconName: "play"; accent: true; hint: "启动"; width: tile.featured ? 82 : 42; height: tile.featured ? 34 : 42; label: tile.featured ? "启动" : ""; enabled: !backend.busy; onClicked: tile.launchRequested(tile.game) }
                IconButton { iconName: "settings"; overArtwork: tile.featured; hint: "设置"; height: tile.featured ? 34 : 42; enabled: !backend.busy; onClicked: tile.detailsRequested(tile.game) }
                IconButton { iconName: "cloud"; overArtwork: tile.featured; hint: "存档记录"; height: tile.featured ? 34 : 42; enabled: !backend.busy; onClicked: tile.cloudRequested(tile.game) }
            }
        }
    }
    Column {
        visible: !tile.featured
        anchors { left: parent.left; right: parent.right; top: coverArea.bottom; topMargin: 9 }
        TitleLabel { objectName: "gameTitle"; scrolling: tile.scrolling; width: parent.width; text: tile.game.name || ""; font.pixelSize: tile.featured ? 16 : 13; font.weight: Font.DemiBold; color: Theme.text; elide: Text.ElideRight; }
    }
}
