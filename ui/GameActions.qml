import QtQuick
import QtQuick.Layouts
Item {
    id: actions
    property var game: ({})
    property bool light: false
    implicitWidth: 220; implicitHeight: 42
    signal launchRequested(var game)
    signal detailsRequested(var game)
    signal cloudRequested(var game)
    signal removeRequested(var game)
    function controllerControls() { var result=[];for(var i=0;i<actionRepeater.count;i++) { var item=actionRepeater.itemAt(i);if(item && item.visible && item.enabled) result.push(item) };return result }
    RowLayout {
        anchors.fill: parent; spacing: 6
        Repeater {
            id: actionRepeater
            model: ["play","settings","cloud","delete"]
            IconButton {
                required property int index; required property string modelData
                objectName: "experience-action-"+modelData
                Layout.fillWidth: true; Layout.preferredHeight: 40
                iconName: modelData; label: index===0 ? "启动" : ""; bare: true
                lightIcon: actions.light; enabled: !!actions.game.id && !backend.busy
                hint: index===0 ? "启动游戏" : index===1 ? "游戏设置" : index===2 ? "存档记录" : "移除游戏"
                transferState: index===2 ? backend.transferStates[actions.game.id] || "idle" : "idle"
                onClicked: { if(index===0) actions.launchRequested(actions.game);else if(index===1) actions.detailsRequested(actions.game);else if(index===2) actions.cloudRequested(actions.game);else actions.removeRequested(actions.game) }
            }
        }
    }
}
