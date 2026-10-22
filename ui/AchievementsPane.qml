import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ControllerForm.js" as Form

ScrollView {
    id: pane
    objectName: "achievementsPane"
    property string gameId: ""
    readonly property var info: backend.achievements.state
    property bool loaded: false
    property bool dirty: false
    readonly property bool localGame: !backend.libraryGame(gameId).platform || backend.libraryGame(gameId).platform==="local"
    clip: true
    contentWidth: availableWidth
    function loadFor(ident) { gameId=ident;loaded=false;dirty=false;query.text=backend.libraryGame(ident).name || "";backend.achievements.openFor(ident) }
    function save() { dirty=false;backend.achievements.save(gameId,{enabled:enabledToggle.checked,notifications:notifications.checked,source:source.text}) }
    function controllerInput(command) {
        if(list.activeFocus) {
            if(command==="up" && list.currentIndex<=0) { Form.reveal(preview,pane);return true }
            if(command==="up" || command==="down") { list.currentIndex=Math.max(0,Math.min(list.count-1,list.currentIndex+(command==="up" ? -1 : 1)));list.positionViewAtIndex(list.currentIndex,ListView.Contain);return true }
            return true
        }
        if(command==="down" && pane.Window.window.activeFocusItem===preview && list.count) { list.currentIndex=0;Form.reveal(list,pane);return true }
        return Form.handle([enabledToggle,notifications,setup,query,searchButton,candidates,chooseCandidate,appid,matchButton,source,sourceChoice,pickSource,importSchema,refreshButton,preview],pane.Window.window.activeFocusItem,command,pane)
    }
    Connections {
        target: backend.achievements
        function onChanged() {
            if(pane.info.ident!==pane.gameId || pane.info.busy) return
            if(!pane.loaded) { setup.checked=!pane.info.has_schema || !pane.info.source;pane.loaded=true }
            if(!pane.dirty) { enabledToggle.checked=pane.info.enabled!==false;notifications.checked=pane.info.notifications!==false;source.text=pane.info.source || "";appid.text=pane.info.appid || "" }
        }
    }
    ColumnLayout {
    width: pane.availableWidth
    spacing: 10
    RowLayout {
        Layout.fillWidth: true
        Label { text: "本地成就";font.pixelSize: 21;font.bold: true;Layout.fillWidth: true }
        Label { text: (pane.info.unlocked || 0)+" / "+(pane.info.total || 0)+" 已解锁";color: Theme.accent }
        Switch { id: enabledToggle;objectName: "achievementEnabled";text: "监听";enabled: pane.localGame && !pane.info.busy;onToggled: pane.dirty=true }
        Switch { id: notifications;objectName: "achievementNotifications";text: "游戏内弹窗";enabled: pane.localGame && !pane.info.busy;onToggled: pane.dirty=true }
    }
    ProgressBar { Layout.fillWidth: true;from: 0;to: Math.max(1,pane.info.total || 0);value: pane.info.unlocked || 0 }
    Label { Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;text: "读取游戏生成的成就记录。首次导入不弹窗；普通窗口、无边框及 Anime4K 放大时，新解锁会显示在游戏上方。";font.pixelSize: 12 }
    AppButton { id: setup;objectName: "achievementSetup";visible: pane.localGame;text: checked ? "收起匹配设置" : "匹配与记录设置";checkable: true }
    Label { visible: setup.checked;Layout.fillWidth: true;wrapMode: Text.Wrap;font.pixelSize: 12;color: Theme.secondary;text: "需要游戏生成可读取的成就记录；只有成就列表不能自动判定解锁。部分独占全屏请改为无边框。" }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: query;objectName: "achievementSearch";Layout.fillWidth: true;placeholderText: "搜索游戏名称";onAccepted: backend.achievements.search(pane.gameId,text) }
        AppButton { id: searchButton;objectName: "achievementSearchButton";text: "搜索匹配";enabled: !pane.info.busy;onClicked: backend.achievements.search(pane.gameId,query.text) }
    }
    RowLayout {
        visible: (pane.info.candidates || []).length>0 && pane.localGame && setup.checked;Layout.fillWidth: true
        AppComboBox { id: candidates;objectName: "achievementCandidates";Layout.fillWidth: true;model: pane.info.candidates || [];textRole: "name" }
        AppButton { id: chooseCandidate;text: "使用此版本";enabled: !pane.info.busy && candidates.currentIndex>=0;onClicked: backend.achievements.match(pane.gameId,pane.info.candidates[candidates.currentIndex].appid) }
    }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: appid;objectName: "achievementAppId";Layout.fillWidth: true;placeholderText: "Steam App ID（从游戏资料自动识别）" }
        AppButton { id: matchButton;objectName: "achievementMatch";text: "匹配成就";enabled: !pane.info.busy && appid.text.length>0;onClicked: backend.achievements.match(pane.gameId,appid.text.trim()) }
    }
    RowLayout {
        visible: pane.localGame && setup.checked;Layout.fillWidth: true
        AppTextField { id: source;objectName: "achievementSource";Layout.fillWidth: true;placeholderText: "成就记录 JSON / INI（不是普通存档）";selectByMouse: true;onTextEdited: pane.dirty=true }
        AppButton { id: pickSource;text: "选择记录";enabled: !pane.info.busy;onClicked: backend.achievements.pickSource(pane.gameId) }
    }
    AppComboBox {
        id: sourceChoice;objectName: "achievementSourceChoice";Layout.fillWidth: true;visible: setup.checked && (pane.info.sources || []).length>1
        model: pane.info.sources || [];displayText: currentIndex>=0 ? currentText : "选择本次账号的记录";currentIndex: -1
        onActivated: { source.text=currentText;pane.dirty=true }
    }
    RowLayout {
        Layout.fillWidth: true;spacing: 8
        AppButton { id: importSchema;visible: pane.localGame && setup.checked;text: "导入定义";enabled: !pane.info.busy;onClicked: backend.achievements.importSchema(pane.gameId) }
        AppButton { id: refreshButton;visible: pane.localGame && setup.checked;text: "重新检测";enabled: !pane.info.busy;onClicked: backend.achievements.openFor(pane.gameId) }
        Item { Layout.fillWidth: true }
        AppButton { id: preview;objectName: "achievementPreview";text: "预览弹窗";onClicked: backend.achievements.preview() }
    }
    RowLayout {
        Layout.fillWidth: true
        AppBusyIndicator { running: pane.info.busy;visible: running;implicitWidth: 20;implicitHeight: 20 }
        Label { objectName: "achievementStatus";Layout.fillWidth: true;wrapMode: Text.Wrap;text: pane.info.message || "";color: Theme.secondary;font.pixelSize: 12 }
    }
    ListView {
        id: list;objectName: "achievementList";Layout.fillWidth: true;Layout.preferredHeight: Math.max(180,pane.availableHeight-list.y-12);clip: true;spacing: 4
        model: pane.info.ident===pane.gameId ? (pane.info.rows || []) : [];currentIndex: -1;reuseItems: true;boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}
        delegate: Rectangle {
            required property var modelData
            required property int index
            width: list.width;height: Math.max(88,details.implicitHeight+20);radius: Theme.controlRadius
            color: modelData.unlocked ? Theme.selection : Theme.surface
            border.color: list.activeFocus && list.currentIndex===index ? Theme.accent : Theme.outline
            RowLayout {
                anchors.fill: parent;anchors.margins: 10;spacing: 14
                Item {
                    Layout.preferredWidth: 56;Layout.preferredHeight: 56
                    Label { anchors.centerIn: parent;text: modelData.unlocked ? "★" : "☆";color: modelData.unlocked ? Theme.accent : Theme.secondary;font.pixelSize: 30;visible: !icon.visible }
                    Image { id: icon;anchors.fill: parent;source: modelData.iconUrl || "";asynchronous: true;visible: status===Image.Ready && (!modelData.hidden || modelData.unlocked);fillMode: Image.PreserveAspectFit;opacity: modelData.unlocked ? 1 : .45 }
                }
                ColumnLayout {
                    id: details;Layout.fillWidth: true;spacing: 4
                    Label { text: modelData.name;font.bold: true;Layout.fillWidth: true;elide: Text.ElideRight }
                    Label { text: modelData.description;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;font.pixelSize: 12;maximumLineCount: 2;elide: Text.ElideRight }
                    Label { visible: modelData.max>0 && !modelData.unlocked;text: modelData.progress+" / "+modelData.max;color: Theme.secondary;font.pixelSize: 12 }
                }
                Label { text: modelData.unlocked ? modelData.unlocked_at : "未解锁";color: modelData.unlocked ? Theme.accent : Theme.secondary;font.pixelSize: 11 }
            }
        }
        Label { anchors.centerIn: parent;width: parent.width-30;wrapMode: Text.Wrap;horizontalAlignment: Text.AlignHCenter;visible: !list.count;text: "尚无成就列表\n匹配游戏或导入定义后，在这里查看解锁进度。";color: Theme.secondary }
    }
    }
}
