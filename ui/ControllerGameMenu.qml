import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: menu
    objectName: "controllerGameMenu"
    modal: true; focus: true; closePolicy: Popup.NoAutoClose
    enter: Transition { NumberAnimation { property: "opacity";from: 0;to: 1;duration: Theme.motion ? 80 : 0 } }
    exit: Transition {}
    Overlay.modal: Rectangle { color: "#bb000000" }
    property var game: ({})
    property int selectedAction: 0
    property bool useLaunchTransition: false
    signal launchRequested(var game)
    signal settingsRequested(var game)
    readonly property var actions: ["启动游戏",game.favorite ? "取消收藏" : "收藏","本地备份","本地备份并上传","游戏设置","关闭"]
    title: game.name || "游戏"
    function showGame(record) { game=record;selectedAction=0;open() }
    function choose(index) {
        if(index===0) { if(useLaunchTransition) launchRequested(game);else backend.launch(game.id) }
        else if(index===1) { backend.toggleFavorite(game.id);game=Object.assign({},game,{favorite:!game.favorite}) }
        else if(index===2) backend.localSave(game.id)
        else if(index===3) backend.cloudSave(game.id)
        else if(index===4) { close();settingsRequested(game) }
        if(index===0 || index===5) close()
    }
    function usable(index) { return index>=4 || !backend.busy && (index<2 || !!game.saveSet && (index!==3 || !!backend.settings.cloud_folder)) }
    function controllerInput(command) {
        if(!visible) return false
        if(command==="back") close()
        else if(command==="activate") { if(usable(selectedAction)) choose(selectedAction) }
        else if(["up","down","left","right","next","previous"].indexOf(command)>=0) {
            var step=["up","left","previous"].indexOf(command)>=0 ? -1 : 1
            var next=selectedAction+step
            while(next>=0 && next<actions.length && !usable(next)) next+=step
            if(next>=0 && next<actions.length && selectedAction!==next) { selectedAction=next;backend.navigationMoved() }
        }
        return true
    }
    contentItem: ColumnLayout {
        Label { text: "发行日期："+(menu.game.release_date || "未知"); color: Theme.secondary }
        Label { text: (menu.game.tags || []).join(" · "); Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        Repeater {
            model: menu.actions
            AppButton { required property int index; required property string modelData; text: modelData; Layout.fillWidth: true; enabled: menu.usable(index); highlighted: menu.selectedAction===index; onClicked: menu.choose(index) }
        }
        Label { text: "A 确认  B 返回"; Layout.fillWidth: true; color: Theme.secondary }
    }
}
