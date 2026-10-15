import QtQuick
import QtQuick.Window
import QtQuick.Controls
AbstractButton {
    id: control
    property string iconName: "play"
    property string hint: ""
    property string label: ""
    property bool accent: false
    property bool overArtwork: false
    readonly property color foreground: accent ? Theme.onAccent : overArtwork ? "#ffffff" : Theme.text
    property string transferState: "idle"
    property bool loading: transferState === "saving" || transferState === "uploading"
    implicitWidth: 42
    implicitHeight: 42
    padding: 0
    hoverEnabled: !backend.controllerMode
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
    ToolTip.visible: hovered
    ToolTip.text: hint
    ToolTip.delay: 350
    Accessible.name: hint
    background: Rectangle {
        radius: 8
        x: 0; y: 0; width: control.width; height: control.height
        color: control.transferState === "success" ? "#34502a" : control.transferState === "failed" ? "#56302d" : control.accent ? (control.hovered ? Qt.lighter(Theme.accent,1.12) : Theme.accent) : control.overArtwork ? (control.hovered ? "#80505050" : "#55000000") : (control.hovered ? Theme.hover : "transparent")
        border.color: control.activeFocus ? Theme.accent : "transparent"
    }
    contentItem: Item {
        x: 0; y: 0; width: control.width; height: control.height
        Image {
            id: glyph
            anchors.verticalCenter: parent.verticalCenter
            x: control.label ? Math.max(5,(control.width-(20+6+caption.implicitWidth))/2) : (parent.width-width)/2
            width: 20; height: 20
            visible: !control.loading
            source: backend.iconSource(control.transferState === "success" ? "success" : control.transferState === "failed" ? "failed" : control.iconName,(control.transferState === "success" || control.transferState === "failed" ? "#ffffff" : control.foreground).toString())
            sourceSize: Qt.size(Math.ceil(width*Screen.devicePixelRatio), Math.ceil(height*Screen.devicePixelRatio))
            opacity: control.enabled ? 1 : 0.4
        }
        Text { id: caption; anchors.verticalCenter: parent.verticalCenter; x: glyph.x+glyph.width+6; text: control.label; visible: !!text; color: control.foreground; font.pixelSize: 12; font.weight: Font.DemiBold }
        BusyIndicator { anchors.centerIn: parent; width: 30; height: 30; running: control.loading; visible: running }
    }
    Rectangle {
        anchors.fill: parent; anchors.margins: -3; z: 10; radius: 6; color: "transparent"
        border.color: Theme.accent; border.width: 2
        visible: control.activeFocus && control.accent && control.enabled
    }
}
