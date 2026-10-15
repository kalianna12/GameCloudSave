import QtQuick
import QtQuick.Controls as C

C.ComboBox {
    id: control
    property int controllerIndex: 0
    property bool controllerBrowsing: false
    property bool wrapOptions: false
    property bool quiet: false
    function controllerInput(command) {
        if(command!=="activate" && command!=="back" && command!=="up" && command!=="down") return false
        if(!popup.visible) {
            if(command!=="activate") return false
            controllerIndex=Math.max(0,currentIndex);controllerBrowsing=true;popup.open();return true
        }
        if(!controllerBrowsing) controllerIndex=Math.max(0,highlightedIndex>=0 ? highlightedIndex : currentIndex)
        controllerBrowsing=true
        if(command==="up" || command==="down") {
            var previous=controllerIndex
            controllerIndex=Math.max(0,Math.min(count-1,controllerIndex+(command==="up" ? -1 : 1)))
            if(previous!==controllerIndex) backend.navigationMoved()
            items.positionViewAtIndex(controllerIndex,ListView.Contain)
        } else if(command==="activate") { currentIndex=controllerIndex;activated(currentIndex);popup.close();forceActiveFocus() }
        else { popup.close();forceActiveFocus() }
        return true
    }
    implicitWidth: 180
    implicitHeight: 38
    leftPadding: 11; rightPadding: 32; topPadding: 6; bottomPadding: 6
    topInset: 0; bottomInset: 0
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    hoverEnabled: !backend.controllerMode
    contentItem: Text {
        text: control.displayText; font: control.font; color: Theme.text
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width-width-12; y: (control.height-height)/2
        text: "▾"; font.pixelSize: 14; color: Theme.secondary
    }
    background: Rectangle {
        radius: 9; color: control.hovered ? Theme.hover : control.quiet ? "transparent" : Theme.surface
        border.color: control.activeFocus ? Theme.accent : control.quiet ? "transparent" : Theme.outline
        border.width: control.activeFocus ? 2 : 1
        opacity: control.enabled ? 1 : .6
    }
    delegate: C.ItemDelegate {
        required property int index
        hoverEnabled: !backend.controllerMode
        width: control.width; implicitHeight: Math.max(38,contentItem.implicitHeight+16); font: control.font
        text: control.textAt(index); highlighted: (control.controllerBrowsing ? control.controllerIndex : control.highlightedIndex)===index
        onHoveredChanged: if(hovered) control.controllerBrowsing=false
        contentItem: Text {
            text: parent.text; font: control.font; color: Theme.text
            verticalAlignment: Text.AlignVCenter; elide: control.wrapOptions ? Text.ElideNone : Text.ElideRight
            wrapMode: control.wrapOptions ? Text.WrapAnywhere : Text.NoWrap
        }
        background: Rectangle { color: parent.highlighted || parent.hovered ? Theme.hover : Theme.surface }
    }
    popup: C.Popup {
        focus: true
        onClosed: control.controllerBrowsing=false
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.motion ? 100 : 0 } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.motion ? 100 : 0 } }
        y: control.height+4; width: control.width; padding: 4
        implicitHeight: Math.min(320, items.contentHeight+8)
        background: Rectangle { color: Theme.surface; radius: 5; border.color: Theme.border }
        contentItem: ListView {
            id: items; clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.controllerBrowsing ? control.controllerIndex : control.highlightedIndex
            C.ScrollBar.vertical: C.ScrollBar {}
        }
    }
}
