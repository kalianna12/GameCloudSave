import QtQuick
import QtQuick.Window
import QtQuick.Templates as C
C.BusyIndicator {
    id: control
    implicitWidth: 24; implicitHeight: 24; padding: 0
    readonly property bool animate: running && visible && !!Window.window && Window.window.visible && Window.window.active && Theme.motion
    // Material's fade Animator can remain scheduled after its control is hidden.
    // This spinner has no fade and stops its sole animator when work ends.
    contentItem: Item {
        id: spinner
        Repeater {
            model: 8
            Rectangle {
                required property int index
                width: Math.max(2,spinner.width*.13); height: width; radius: width/2
                x: spinner.width/2+Math.cos(index*Math.PI/4)*spinner.width*.34-width/2
                y: spinner.height/2+Math.sin(index*Math.PI/4)*spinner.height*.34-height/2
                color: Theme.accent; opacity: .2+index*.1
            }
        }
        RotationAnimator { target: spinner; from: 0; to: 360; duration: 900; loops: Animation.Infinite; running: control.animate }
    }
}
