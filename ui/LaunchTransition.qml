import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
Item {
    id: launch
    objectName: "launchTransition"
    property var game: ({})
    property string design: "shelf"
    property bool running: false
    property real progress: 0
    property real fade: 1
    property bool sent: false
    property bool animationDone: false
    property bool ready: false
    readonly property var launchStatus: backend.launchState
    visible: running
    signal committed(var game)
    function begin(record,style) {
        if(running) return
        game=record;design=style;sent=false;ready=false;animationDone=false;progress=0;fade=1;running=true
        backend.beginLaunchPresentation(launch.Window.window)
        backend.playLaunchSound()
        intro.restart();sendTimer.interval=Theme.motion ? 120 : 0;sendTimer.restart()
    }
    function commit() { if(running && !sent) { sent=true;committed(game) } }
    function maybeFinish() { if(running && animationDone && ready) Qt.callLater(function() { if(launch.running && launch.animationDone && launch.ready && !outro.running) outro.restart() }) }
    function cancel() {
        backend.stopLaunchSound()
        sendTimer.stop();intro.stop();outro.stop()
        if(sent) backend.cancelLaunchWait();else backend.releaseLaunchPresentation()
        running=false;progress=0
    }
    function controllerInput(command) { if(command==="back") cancel();else if(command==="activate" && launchStatus.phase==="timeout") backend.continueLaunchWait();return true }
    onLaunchStatusChanged: {
        if(!running || !sent || launchStatus.ident!==game.id) return
        ready=launchStatus.phase==="ready";maybeFinish()
    }
    opacity: fade
    Rectangle { anchors.fill: parent; color: "#0c1018" }
    Image { anchors.fill: parent; source: launch.game.backgroundUrl || launch.game.coverHighUrl || launch.game.coverUrl || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 1280; opacity: .1+launch.progress*.08 }
    Rectangle { anchors.fill: parent; gradient: Gradient { GradientStop { position: 0; color: "#800c1018" } GradientStop { position: .5; color: "#400c1018" } GradientStop { position: 1; color: "#ff0c1018" } } }
    MouseArea { anchors.fill: parent }
    Item {
        id: jacket
        width: Math.min(240,launch.width*.2); height: width*1.42
        x: (parent.width-width)/2; y: Math.max(24,(parent.height-height-140)/2)
        scale: .82+launch.progress*.18; opacity: .15+launch.progress*.85
        transform: Rotation { origin.x: jacket.width/2; origin.y: jacket.height/2; axis.y: 1; axis.x: 0; axis.z: 0; angle: launch.design==="shelf" ? -24*(1-launch.progress) : 0 }
        Rectangle { anchors.fill: parent; anchors.margins: -8; radius: 12; color: Theme.selection; border.color: Theme.accent; border.width: 1 }
        Image { anchors.fill: parent; source: launch.game.coverHighUrl || launch.game.coverUrl || ""; fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 720 }
    }
    ColumnLayout {
        anchors.top: jacket.bottom; anchors.topMargin: 26; anchors.horizontalCenter: parent.horizontalCenter; width: Math.min(600,launch.width-60); spacing: 14
        Label { text: launch.game.name || ""; color: "#f3f5f7"; font.pixelSize: 24; font.weight: Font.DemiBold; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight }
        Rectangle { Layout.alignment: Qt.AlignHCenter; width: 180; height: 2; color: "#334051"; Rectangle { width: parent.width*launch.progress; height: 2; color: Theme.accent } }
        Label { objectName: "launchMessage"; text: !launch.sent ? "正在准备启动" : launch.launchStatus.ident===launch.game.id ? launch.launchStatus.message : "正在启动游戏"; color: "#bdcada"; Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            AppButton { objectName: "launchContinue"; visible: launch.launchStatus.phase==="timeout" && launch.sent; text: "继续等待"; onClicked: backend.continueLaunchWait() }
            AppButton { objectName: "launchCancel"; text: launch.sent ? "返回游戏库" : "取消启动"; onClicked: launch.cancel() }
        }
    }
    Timer { id: sendTimer; onTriggered: launch.commit() }
    SequentialAnimation {
        id: intro
        NumberAnimation { target: launch; property: "progress"; to: 1; duration: Theme.motion ? 900 : 0; easing.type: Easing.OutCubic }
        ScriptAction { script: { launch.animationDone=true;launch.maybeFinish() } }
    }
    SequentialAnimation {
        id: outro
        ScriptAction { script: backend.finishLaunchPresentation() }
        NumberAnimation { target: launch; property: "fade"; to: 0; duration: Theme.motion ? 160 : 0 }
        ScriptAction { script: launch.running=false }
    }
}
