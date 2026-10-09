import QtQuick
import QtQuick.Controls as C

C.ComboBox {
    id: control
    implicitWidth: 180
    implicitHeight: 38
    leftPadding: 11; rightPadding: 32; topPadding: 6; bottomPadding: 6
    topInset: 0; bottomInset: 0
    font.family: "Microsoft YaHei UI"; font.pixelSize: 13
    hoverEnabled: true
    contentItem: Text {
        text: control.displayText; font: control.font; color: Theme.text
        verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: Text {
        x: control.width-width-12; y: (control.height-height)/2
        text: "▾"; font.pixelSize: 14; color: Theme.secondary
    }
    background: Rectangle {
        radius: 5; color: control.hovered ? Theme.hover : Theme.surface
        border.color: control.activeFocus ? Theme.text : Theme.border
        border.width: control.activeFocus ? 2 : 1
        opacity: control.enabled ? 1 : .6
    }
    delegate: C.ItemDelegate {
        required property int index
        width: control.width; implicitHeight: 38; font: control.font
        text: control.textAt(index); highlighted: control.highlightedIndex===index
        contentItem: Text {
            text: parent.text; font: control.font; color: Theme.text
            verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        background: Rectangle { color: parent.highlighted || parent.hovered ? Theme.hover : Theme.surface }
    }
    popup: C.Popup {
        y: control.height+4; width: control.width; padding: 4
        implicitHeight: Math.min(320, items.contentHeight+8)
        background: Rectangle { color: Theme.surface; radius: 5; border.color: Theme.border }
        contentItem: ListView {
            id: items; clip: true; implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            C.ScrollBar.vertical: C.ScrollBar {}
        }
    }
}
