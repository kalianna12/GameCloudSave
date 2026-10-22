import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Dialog {
    id: keyboard
    title: ""
    modal: true;focus: true;closePolicy: Popup.NoAutoClose
    exit: Transition {}
    Overlay.modal: Rectangle { color: "#c8000000" }
    padding: 24
    background: Rectangle { color: Theme.surface;radius: 2;border.width: 2;border.color: Theme.border }
    readonly property real keyHeight: Math.max(32,Math.min((width-leftPadding-rightPadding-50)/11,(parent.height-210)/5,110))
    property alias value: editor.text
    property bool upper: false
    property bool chinese: false
    property bool candidates: false
    property bool finishing: false
    readonly property bool composing: editor.inputMethodComposing || backend.searchIme.pending
    property string inputNotice: ""
    property int selectedKey: 0
    property int cursorRow: 0
    property int cursorColumn: 0
    readonly property var letters: (upper ? "1234567890QWERTYUIOPASDFGHJKL-ZXCVBNM,.!" : "1234567890qwertyuiopasdfghjkl-zxcvbnm,.!").split("")
    signal submitted(string value)
    signal cancelled()
    signal returned()
    function cellAt(row,column) { return column===10 ? row===0 ? 40 : row<3 ? 41 : 42 : row<4 ? row*10+column : column<2 ? 43 : column<8 ? 44 : 45 }
    function selectKey(index) {
        selectedKey=index
        if(index<40) { cursorRow=Math.floor(index/10);cursorColumn=index%10 }
        else if(index<43) { cursorRow=index===40 ? 0 : index===41 ? 1 : 3;cursorColumn=10 }
        else { cursorRow=4;cursorColumn=index===43 ? 0 : index===44 ? 2 : 8 }
    }
    function moveKey(command) {
        var row=cursorRow,column=cursorColumn,dr=command==="up" ? -1 : command==="down" ? 1 : 0,dc=command==="left" ? -1 : command==="right" ? 1 : 0
        do { row+=dr;column+=dc;if(row<0 || row>4 || column<0 || column>10) return } while(cellAt(row,column)===selectedKey)
        cursorRow=row;cursorColumn=column;selectedKey=cellAt(row,column);backend.navigationMoved()
    }
    function start(text) { value=text;selectKey(0);candidates=false;finishing=false;inputNotice="";open();Qt.callLater(function() { editor.forceActiveFocus();editor.cursorPosition=editor.length }) }
    function complete() { if(!finishing) return;finishing=false;submitted(value);close() }
    function finish() { finishing=true;Qt.inputMethod.commit();if(composing) backend.searchIme.key("space");else complete() }
    function resetComposition() { if(composing) backend.searchIme.key("escape");Qt.inputMethod.reset();backend.searchIme.committed();candidates=false }
    function cancel() { finishing=false;resetComposition();close();cancelled() }
    function toggleChinese() {
        editor.forceActiveFocus();resetComposition()
        var next=!chinese
        if(backend.searchIme.setChinese(next)) { chinese=next;inputNotice=next ? "系统中文输入法：输入拼音，上键进入候选，A 选词。" : "" }
        else inputNotice="请先在 Windows 添加中文输入法，也可直接用实体键盘输入。"
    }
    function insert(text) {
        editor.forceActiveFocus()
        if(chinese && /^[a-zA-Z0-9]$/.test(text)) { backend.searchIme.key(text);return }
        if(editor.selectedText) editor.remove(editor.selectionStart,editor.selectionEnd)
        editor.insert(editor.cursorPosition,text)
    }
    function erase() { editor.forceActiveFocus();if(composing) backend.searchIme.key("backspace");else if(editor.selectedText) editor.remove(editor.selectionStart,editor.selectionEnd);else if(editor.cursorPosition>0) editor.remove(editor.cursorPosition-1,editor.cursorPosition) }
    function press(index) {
        if(index<40) insert(letters[index])
        else if(index===40) erase()
        else if(index===41) finish()
        else if(index===42) cancel()
        else if(index===43) upper=!upper
        else if(index===44) { editor.forceActiveFocus();if(composing) backend.searchIme.key("space");else insert(" ") }
        else { resetComposition();value="" }
    }
    function controllerInput(command) {
        if(!visible) return false
        editor.forceActiveFocus()
        if(command==="search") { resetComposition();close();returned();return true }
        if(command==="back") { if(composing) resetComposition();else cancel();return true }
        if(command==="favorite") { erase();return true }
        if(command==="previous") { resetComposition();value="";return true }
        if(command==="next") { toggleChinese();return true }
        if(command==="history") { press(44);return true }
        if(command==="case") { upper=!upper;return true }
        if(command==="menu") { finish();return true }
        if(candidates && composing) {
            if(command==="activate") { backend.searchIme.key("space");candidates=false }
            else if(["left","right","up","down"].indexOf(command)>=0) backend.searchIme.key(command)
            return true
        }
        candidates=false
        if(command==="activate") { press(selectedKey);return true }
        if(command==="up" && selectedKey<10 && composing) { candidates=true;backend.searchIme.key("down");return true }
        if(["left","right","up","down"].indexOf(command)>=0) moveKey(command)
        return true
    }
    onClosed: { backend.searchIme.end();chinese=false;candidates=false }
    contentItem: ColumnLayout {
        spacing: 28
        RowLayout {
            Layout.fillWidth: true
            AppTextField {
                id: editor;objectName: "keyboardValue";Layout.fillWidth: true;implicitHeight: 64;font.pixelSize: 24;selectByMouse: true
                placeholderText: "搜索名称 / 拼音 / 首字母 / 标签";inputMethodHints: Qt.ImhNone
                onTextEdited: { backend.searchIme.committed();if(keyboard.finishing) Qt.callLater(keyboard.complete) }
                Keys.onReturnPressed: function(event) { if(!keyboard.composing) keyboard.finish();else event.accepted=false }
                Keys.onEscapePressed: function(event) { if(!keyboard.composing) keyboard.cancel();else event.accepted=false }
            }
            AppButton { text: keyboard.chinese ? "中文" : "EN";implicitHeight: 64;onClicked: keyboard.toggleChinese() }
        }
        Label { visible: !!keyboard.inputNotice;text: keyboard.inputNotice;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary }
        GridLayout {
            Layout.fillWidth: true;columns: 11;rowSpacing: 5;columnSpacing: 5
            Repeater {
                model: 46
                AppButton {
                    id: keyControl
                    required property int index
                    readonly property bool letter: index<40
                    objectName: "keyboardKey-"+index
                    Layout.row: letter ? Math.floor(index/10) : index===40 ? 0 : index===41 ? 1 : index===42 ? 3 : 4
                    Layout.column: letter ? index%10 : index<43 ? 10 : index===43 ? 0 : index===44 ? 2 : 8
                    Layout.rowSpan: index===41 || index===42 ? 2 : 1
                    Layout.columnSpan: index===43 || index===45 ? 2 : index===44 ? 6 : 1
                    Layout.fillWidth: true;Layout.fillHeight: true;Layout.minimumWidth: 0
                    implicitHeight: keyboard.keyHeight;font.pixelSize: Math.max(16,Math.min(28,keyboard.width*.023))
                    text: letter ? keyboard.letters[index] : ["⌫","完成","取消","大写","空格","清空"][index-40]
                    contentItem: Item {
                        GridLayout {
                            anchors.centerIn: parent;columns: keyControl.index===41 || keyControl.index===42 ? 1 : 2;rowSpacing: 12;columnSpacing: 10
                            Rectangle {
                                visible: !keyControl.letter
                                Layout.alignment: Qt.AlignCenter
                                implicitWidth: keyControl.index===45 ? 32 : 26;implicitHeight: 26
                                radius: keyControl.index===43 || keyControl.index===45 ? 4 : 13
                                color: "transparent";border.width: 1.5;border.color: Theme.text
                                Label { anchors.centerIn: parent;text: ["X","☰","B","R↓","Y","LB"][keyControl.index-40] || "";color: Theme.text;font.pixelSize: 15;font.bold: true }
                            }
                            Label {
                                Layout.alignment: Qt.AlignCenter
                                text: keyControl.index===43 && keyboard.upper ? "小写" : keyControl.text
                                color: Theme.text;font: keyControl.font
                            }
                        }
                    }
                    background: Rectangle {
                        radius: 2;color: keyControl.hovered ? Theme.hover : Theme.surface
                        border.width: keyboard.selectedKey===keyControl.index && !keyboard.candidates ? 3 : 1
                        border.color: keyboard.selectedKey===keyControl.index && !keyboard.candidates ? Theme.accent : Theme.border
                    }
                    onClicked: { keyboard.selectKey(index);keyboard.press(index) }
                }
            }
        }
        Label { text: "A 输入 / 选词 · X 删除 · Y 空格 · LB 清空 · RB 中英 · 按下右摇杆 大小写 · Menu 完成 · B 返回";Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;font.pixelSize: 12 }
    }
}
