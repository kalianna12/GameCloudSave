import QtQuick
import QtQuick.Controls
Item {
    id: book
    property var game: ({})
    property bool selected: false
    property bool spines: false
    property bool suspended: false
    property bool picked: false
    property real sunlight: 0
    property real coverWidth: 156
    readonly property bool raised: effect.available && (effect.pointerActive || selected && (backend.controllerMode || picked))
    readonly property real lift: Theme.motion && raised ? 22 : 0
    property real opening: spines ? (raised ? -8 : -88) : 0
    signal chosen()
    signal opened()
    HoverHandler { id: bookHover;enabled: !backend.controllerMode }
    implicitWidth: spines ? 66 : coverWidth+14
    implicitHeight: coverWidth*1.42+88
    z: raised ? 10 : 0
    Rectangle {
        x: 8; y: book.coverWidth*1.42+33; width: book.spines ? 46 : book.coverWidth+14; height: 13
        radius: 6; color: "#66000000"; opacity: book.raised ? .3 : .7
        scale: book.raised ? .88 : 1
        Behavior on opacity { NumberAnimation { duration: Theme.motion ? 180 : 0 } }
    }
    Rectangle {
        objectName: "bookSpine"; visible: book.spines; x: 6; y: 48-book.lift; width: 46; height: book.coverWidth*1.42; radius: 3
        color: Theme.surface; border.color: book.selected ? Theme.accent : Theme.border; border.width: book.selected ? 3 : 1
        opacity: book.raised ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: Theme.motion ? 150 : 0 } }
        Rectangle { anchors.fill: parent; anchors.margins: 2; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#60000000" } GradientStop { position: .28; color: "#20ffffff" } GradientStop { position: .85; color: "#00000000" } GradientStop { position: 1; color: "#70000000" } } }
        Label { x: (parent.width-width)/2; y: (parent.height-height)/2; width: parent.height-32; height: 24; rotation: 90; text: book.game.name || ""; color: Theme.text; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
        Rectangle { x: 8; y: 12; width: 30; height: 2; color: Theme.accent; opacity: .65 }
        Rectangle { x: 8; y: parent.height-14; width: 30; height: 2; color: Theme.accent; opacity: .65 }
        SelectionFrame { objectName: "spineFocusRing"; selected: book.selected; radius: 3 }
        NewGameBadge { visible: !!book.game.isNew;width: 38;height: 18;anchors.horizontalCenter: parent.horizontalCenter;y: 6 }
    }
    Item {
        id: volume; objectName: "bookVolume"; x: 6; y: 48-book.lift; visible: !book.spines || book.raised
        width: book.coverWidth; height: width*1.42
        transform: [Rotation { origin.x: 0; origin.y: volume.height/2; axis.y: 1; axis.x: 0; axis.z: 0; angle: book.opening+(book.spines ? 0 : effect.yaw*.35) },Rotation { origin.x: volume.width/2; origin.y: volume.height; angle: !book.spines && book.raised && Theme.motion ? -3 : 0 }]
        Behavior on y { NumberAnimation { duration: Theme.motion ? 240 : 0; easing.type: Easing.OutBack; easing.overshoot: .65 } }
        Rectangle { x: 7; y: 3; width: parent.width; height: parent.height-3; color: "#d8cfb9"; radius: 2
            Repeater { model: 4; Rectangle { required property int index; x: parent.width-7+index; width: 1; y: 3; height: parent.height-7; color: index%2 ? "#f1e8d4" : "#ab9e85" } }
        }
        Rectangle {
            id: jacket; objectName: "bookJacket"; anchors.fill: parent; radius: 3; color: Theme.surface; clip: true
            Image { id: art; anchors.fill: parent; source: book.game.coverHighUrl || book.game.coverUrl || ""; asynchronous: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 480 }
            Label { visible: !art.source.toString() || art.status===Image.Error; anchors.centerIn: parent; width: parent.width-28; text: book.game.name || ""; color: Theme.text; font.pixelSize: 18; wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter }
            Rectangle { x: 0; width: 16; height: parent.height; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#b0000000" } GradientStop { position: .48; color: "#70000000" } GradientStop { position: .72; color: "#40ffffff" } GradientStop { position: 1; color: "#10000000" } } }
            Rectangle { x: 18; width: 1; height: parent.height; color: "#30000000" }
            Rectangle { anchors.fill: parent; color: "transparent"; radius: 3; border.color: "#40ffffff"; border.width: 1 }
            Rectangle { anchors.fill: parent; visible: book.sunlight>0; gradient: Gradient { GradientStop { position: 0; color: Qt.rgba(1,.88,.65,book.sunlight*1.5) } GradientStop { position: .65; color: "transparent" } GradientStop { position: 1; color: "#08000000" } } }
            SelectionFrame { objectName: "bookFocusRing"; selected: book.selected; radius: 3 }
            AchievementBadge { id: achievements;gameId: book.game.id || "";revealed: !book.suspended && (bookHover.hovered || book.selected);x: 6;y: book.game.isNew ? 32 : 6;width: 42 }
            NewGameBadge { visible: !!book.game.isNew;x: 6;y: 6 }
            Label { visible: !!book.game.favorite; text: "★"; color: "#ffe0a0"; font.pixelSize: 21; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8; style: Text.Outline; styleColor: "#773b23" }
        }
    }
    Behavior on opening { NumberAnimation { duration: Theme.motion ? 230 : 0; easing.type: Easing.OutCubic } }
    CoverEffects {
        id: effect; x: 6; y: 48; width: book.spines ? 46 : book.coverWidth; height: book.coverWidth*1.42
        surface: jacket; identity: book.game.id || ""; tiltLimit: 12; controllerFocused: selected && backend.controllerMode; suspended: book.suspended
        TapHandler { onTapped: book.chosen(); onDoubleTapped: book.opened() }
    }
    TitleLabel {
        objectName: "bookTitle"; x: 5; y: book.coverWidth*1.42+53; width: book.spines ? 60 : book.coverWidth; height: 24
        text: book.game.name || ""; elide: Text.ElideRight; color: book.selected ? "#fff1c8" : "#ecd5b6"; font.pixelSize: book.spines ? 10 : 11; scrolling: book.suspended
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        background: Rectangle { radius: 3; color: book.selected ? "#5c432a" : "#3b291e"; border.color: book.selected ? Theme.accent : "#886848" }
    }
}
