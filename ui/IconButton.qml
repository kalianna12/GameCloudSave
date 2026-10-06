import QtQuick
import QtQuick.Controls
AbstractButton {
    id: control
    property string iconName: "play"
    property string hint: ""
    property bool accent: false
    property string transferState: "idle"
    property bool loading: transferState === "saving" || transferState === "uploading"
    implicitWidth: 42
    implicitHeight: 42
    padding: 0
    hoverEnabled: true
    leftPadding: 0; rightPadding: 0; topPadding: 0; bottomPadding: 0
    topInset: 0; bottomInset: 0; leftInset: 0; rightInset: 0
    scale: down ? 0.94 : hovered ? 1.06 : 1
    Behavior on scale { NumberAnimation { duration: 110 } }
    ToolTip.visible: hovered
    ToolTip.text: hint
    ToolTip.delay: 350
    Accessible.name: hint
    background: Rectangle {
        radius: 8
        x: 0; y: 0; width: control.width; height: control.height
        color: control.transferState === "success" ? "#315b32" : control.transferState === "failed" ? "#56302d" : control.accent ? (control.hovered ? "#a5f570" : "#8ce34f") : (control.hovered ? "#354039" : "#252e29")
        border.color: control.activeFocus ? "#b5fa85" : "transparent"
    }
    contentItem: Item {
        x: 0; y: 0; width: control.width; height: control.height
        Image {
            id: glyph
            anchors.centerIn: parent
            width: 20; height: 20
            visible: !control.loading
            source: "icons/" + (control.transferState === "success" ? "success" : control.transferState === "failed" ? "failed" : control.iconName) + ".svg"
            sourceSize: Qt.size(20, 20)
            opacity: control.enabled ? 1 : 0.4
        }
        BusyIndicator { anchors.centerIn: parent; width: 30; height: 30; running: control.loading; visible: running }
    }
    onTransferStateChanged: { successPulse.stop(); failureShake.stop(); glyph.scale=1; glyph.rotation=0; if(transferState==="success") successPulse.restart(); else if(transferState==="failed") failureShake.restart() }
    SequentialAnimation { id: successPulse; NumberAnimation { target: glyph; property: "scale"; from: 0.7; to: 1.2; duration: 170 } NumberAnimation { target: glyph; property: "scale"; to: 1; duration: 140 } }
    SequentialAnimation { id: failureShake; NumberAnimation { target: glyph; property: "rotation"; to: -15; duration: 65 } NumberAnimation { target: glyph; property: "rotation"; to: 15; duration: 100 } NumberAnimation { target: glyph; property: "rotation"; to: 0; duration: 65 } }
}
