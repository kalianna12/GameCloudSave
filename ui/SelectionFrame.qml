import QtQuick
Rectangle {
    readonly property bool focusOutlineDecoration: true
    property bool selected: false
    anchors.fill: parent
    z: 100
    radius: 5
    color: "transparent"
    visible: selected
    border.width: selected ? 3 : 0
    border.color: Theme.accent
    Rectangle { anchors.fill: parent; anchors.margins: 3; radius: Math.max(1,parent.radius-2); color: "transparent"; border.width: 1; border.color: "#90000000" }
}
