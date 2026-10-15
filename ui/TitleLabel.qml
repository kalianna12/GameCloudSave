import QtQuick
import QtQuick.Controls
import QtQuick.Window
Label {
    id: title
    property bool scrolling: false
    readonly property bool tooltipVisible: tip.visible
    HoverHandler { id: hover; enabled: !backend.controllerMode && !title.scrolling }
    // An owned popup avoids Qt's shared attached tooltip retaining a different
    // delegate's visibility when switching from pointer to controller input.
    ToolTip {
        id: tip; objectName: "titleToolTip"; parent: title
        text: title.text; delay: 650
        visible: hover.hovered && !backend.controllerMode && !title.scrolling && title.visible && !!title.Window.window && title.Window.window.visible && title.Window.window.active
        exit: Transition { }
    }
}
