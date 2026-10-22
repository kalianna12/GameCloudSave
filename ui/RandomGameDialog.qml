import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Dialog {
    id: dialog
    objectName: "randomGameDialog"
    title: "随机游戏";modal: true;focus: true;width: Math.min(580,parent.width-48)
    Overlay.modal: Rectangle { color: "#99000000" }
    exit: Transition {}
    property var game: ({})
    property int poolSize: 0
    signal launchRequested(var game)
    signal settingsRequested(var game)
    signal redrawRequested()
    function begin(record,count) { game=record;poolSize=count;open();Qt.callLater(function() { launchButton.forceActiveFocus() }) }
    function launch() { if(!game.id || backend.busy) return;close();launchRequested(game) }
    function settings() { close();settingsRequested(game) }
    function controllerInput(command) {
        if(command==="back") close()
        else if(command==="activate") { if(drawButton.activeFocus) redrawRequested();else if(settingsButton.activeFocus) settings();else launch() }
        else if(command==="history") redrawRequested()
        else if(command==="menu") settings()
        else if(command==="favorite" && game.id) { backend.toggleFavorite(game.id);game=backend.libraryGame(game.id) }
        else if(command==="left" || command==="up") drawButton.forceActiveFocus()
        else if(command==="right" || command==="down") launchButton.forceActiveFocus()
        return true
    }
    contentItem: ColumnLayout {
        spacing: 18
        RowLayout {
            spacing: 22
            Image { Layout.preferredWidth: 138;Layout.preferredHeight: 194;source: dialog.game.coverHighUrl || dialog.game.coverUrl || "";asynchronous: true;fillMode: Image.PreserveAspectCrop;sourceSize.width: 400 }
            ColumnLayout {
                Layout.fillWidth: true;spacing: 12
                Label { text: dialog.game.name || "";font.pixelSize: 23;font.bold: true;Layout.fillWidth: true;wrapMode: Text.Wrap }
                Label { text: (dialog.game.tags || []).join(" · ");color: Theme.secondary;Layout.fillWidth: true;wrapMode: Text.Wrap }
                Label { text: dialog.game.release_date || "发行日期未记录";color: Theme.secondary }
                Label { text: "从当前范围 "+dialog.poolSize+" 款游戏中挑选";color: Theme.secondary;Layout.fillWidth: true;wrapMode: Text.Wrap }
                AppButton { id: settingsButton;text: "游戏设置";onClicked: dialog.settings();contentItem: RowLayout { spacing: 7;ControllerGlyph { button: "Menu";Layout.preferredWidth: 23;Layout.preferredHeight: 23 } Label { text: settingsButton.text;color: Theme.text } } }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            AppButton { id: drawButton;objectName: "randomDrawAgain";text: "换一款";onClicked: dialog.redrawRequested();contentItem: RowLayout { spacing: 7;ControllerGlyph { button: "Y";Layout.preferredWidth: 23;Layout.preferredHeight: 23 } Label { text: drawButton.text;color: Theme.text } } }
            Item { Layout.fillWidth: true }
            AppButton { id: launchButton;objectName: "randomLaunch";text: "启动游戏";highlighted: true;enabled: !!dialog.game.id && !backend.busy;onClicked: dialog.launch();contentItem: RowLayout { spacing: 7;ControllerGlyph { button: "A";ink: Theme.onAccent;Layout.preferredWidth: 23;Layout.preferredHeight: 23 } Label { text: launchButton.text;color: Theme.onAccent } } }
        }
    }
}
