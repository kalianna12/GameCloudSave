import QtQuick
import QtQuick.Window
import QtQuick.Templates as T

Item {
    id: focus
    objectName: "controlFocus"
    readonly property var hostWindow: Window.window
    property Item targetControl: null
    // Reparenting the frame changes the control's children. Resolve on focus
    // events instead of binding to that child list, which would form a loop.
    function refreshTarget() { targetControl=findControl(hostWindow ? hostWindow.activeFocusItem : null) }
    onHostWindowChanged: refreshTarget()
    Component.onCompleted: refreshTarget()
    Connections {
        target: focus.hostWindow
        function onActiveFocusItemChanged() { focus.refreshTarget() }
        function onActiveChanged() { focus.refreshTarget() }
    }
    function findControl(item) {
        while(item && item!==hostWindow.contentItem) {
            if(item.focusOutlineProvided===true) return null
            if(item instanceof T.AbstractButton || item instanceof T.Slider || item instanceof T.SpinBox || item instanceof T.ComboBox || item instanceof T.TextField || item instanceof T.TextArea || item instanceof T.RangeSlider || item instanceof T.Dial) {
                for(var i=0;i<item.children.length;i++) if(item.children[i].focusOutlineDecoration===true && item.children[i].selected) return null
                return item
            }
            item=item.parent
        }
        return null
    }
    Rectangle {
        objectName: "controlFocusFrame"
        parent: focus.targetControl || focus
        anchors.fill: parent;anchors.margins: -2
        z: 100;color: "transparent";radius: Theme.controlRadius
        border.color: Theme.accent;border.width: 3
        visible: !!focus.targetControl && !!focus.hostWindow && focus.hostWindow.active && focus.targetControl.visible && focus.targetControl.enabled
    }
}
