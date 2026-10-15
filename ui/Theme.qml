pragma Singleton
import QtQuick
QtObject {
    property var palette: backend.theme || ({})
    readonly property color background: palette.background || "#181a1c"
    readonly property color sidebar: palette.sidebar || "#202326"
    readonly property color surface: palette.surface || "#282c30"
    readonly property color hover: palette.hover || "#353b41"
    readonly property color border: palette.border || "#454d56"
    readonly property color text: palette.text || "#f3f5f7"
    readonly property color secondary: palette.secondary || "#a9b4bf"
    readonly property color accent: palette.accent || "#80c942"
    readonly property color onAccent: palette.onAccent || "#10200a"
    readonly property bool dark: palette.dark !== false
    readonly property bool motion: palette.motion !== false
    readonly property color outline: Qt.rgba(border.r,border.g,border.b,.48)
    readonly property color selection: Qt.rgba(accent.r,accent.g,accent.b,dark ? .12 : .1)
    readonly property int cardFooterHeight: 90
    readonly property real coverAspect: 1.38
}
