import QtQuick
import QtQuick.Controls
Item {
    id: launch
    objectName: "launchTransition"
    property var game: ({})
    property string design: "shelf"
    property bool running: false
    property real progress: 0
    property bool sent: false
    visible: running
    signal committed(var game)
    function begin(record,style) { if(running) return;game=record;design=style;sent=false;progress=0;running=true;sequence.restart() }
    function commit() { if(!sent) { sent=true;committed(game) } }
    function cancel() { if(!sent) { sequence.stop();running=false;progress=0 } }
    Rectangle { anchors.fill: parent; color: "#100e14"; opacity: launch.progress*.9 }
    Rectangle { visible: launch.design==="atlas"; anchors.centerIn: parent; width: 240+launch.progress*200; height: width; radius: width/2; color: "transparent"; border.color: Theme.accent; border.width: 2; opacity: 1-launch.progress }
    Item {
        width: 180; height: 260; anchors.centerIn: parent; opacity: 1-launch.progress*.6
        scale: launch.design==="cinema" ? 1+launch.progress*.7 : 1+launch.progress*.23
        transform: Rotation { origin.x: 90; origin.y: 130; axis.y: 1; axis.x: 0; axis.z: 0; angle: launch.design==="shelf" ? -launch.progress*15 : 0 }
        Image { anchors.fill: parent; source: launch.game.coverHighUrl || launch.game.coverUrl || ""; fillMode: Image.PreserveAspectFit; asynchronous: true }
    }
    Label { anchors.horizontalCenter: parent.horizontalCenter; y: parent.height/2+155; text: launch.game.name || ""; color: "white"; font.pixelSize: 22 }
    MouseArea { anchors.fill: parent }
    SequentialAnimation {
        id: sequence
        NumberAnimation { target: launch; property: "progress"; to: 1; duration: 200; easing.type: Easing.InCubic }
        ScriptAction { script: launch.commit() }
        PauseAnimation { duration: 80 }
        PropertyAction { target: launch; property: "running"; value: false }
    }
}
