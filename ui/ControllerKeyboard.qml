import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Dialog {
    id: keyboard
    title: ""
    modal: true;focus: true;closePolicy: Popup.NoAutoClose
    exit: Transition {}
    padding: 0
    background: Rectangle { color: "transparent";radius: 0 }
    readonly property real keyHeight: Math.max(30,Math.min(width/11,(parent.height-48)/6.8))
    property url backdropUrl: ""
    Overlay.modal: Item {
        Image { anchors.fill: parent;source: keyboard.backdropUrl;fillMode: Image.PreserveAspectCrop;asynchronous: true;sourceSize.width: 1600 }
        Rectangle { anchors.fill: parent;color: "#a6000000" }
    }
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
    contentItem: Item {
        implicitHeight: keyboard.keyHeight*6.8
        AppTextField {
                id: editor;objectName: "keyboardValue";width: parent.width;height: keyboard.keyHeight*.85;font.pixelSize: keyboard.keyHeight*.3;selectByMouse: true
                rightPadding: languageButton.width+16
                Accessible.name: "搜索游戏";inputMethodHints: Qt.ImhNone
                background: Rectangle { color: Theme.dark ? "#303233" : Theme.surface;border.color: Theme.border;border.width: 2;radius: 0 }
                onTextEdited: { backend.searchIme.committed();if(keyboard.finishing) Qt.callLater(keyboard.complete) }
                Keys.onReturnPressed: function(event) { if(!keyboard.composing) keyboard.finish();else event.accepted=false }
                Keys.onEscapePressed: function(event) { if(!keyboard.composing) keyboard.cancel();else event.accepted=false }
                AppButton {
                    id: languageButton;objectName: "keyboardLanguage";anchors.right: parent.right;anchors.verticalCenter: parent.verticalCenter;anchors.rightMargin: 12
                    width: Math.max(76,keyboard.keyHeight);height: Math.min(40,parent.height-8);flat: true;focusPolicy: Qt.NoFocus
                    onClicked: keyboard.toggleChinese()
                    contentItem: RowLayout { spacing: 6;ControllerGlyph { button: "RB";Layout.preferredWidth: 26;Layout.preferredHeight: 23 } Label { text: keyboard.chinese ? "中文" : "EN";color: Theme.secondary;font.pixelSize: 14 } }
                }
        }
        Label { visible: !!keyboard.inputNotice;text: keyboard.inputNotice;anchors.left: parent.left;anchors.right: parent.right;anchors.top: editor.bottom;anchors.topMargin: 10;wrapMode: Text.Wrap;color: Theme.secondary;font.pixelSize: 12 }
        GridLayout {
            objectName: "keyboardGrid";width: parent.width;height: keyboard.keyHeight*5;y: keyboard.keyHeight*1.8
            columns: 11;rowSpacing: 0;columnSpacing: 0;uniformCellWidths: true;uniformCellHeights: true
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
                    implicitHeight: keyboard.keyHeight;font.pixelSize: Math.max(14,keyboard.keyHeight*.29);font.weight: Font.Light
                    text: letter ? keyboard.letters[index] : ["","完 成","取 消","大写","空格","清除"][index-40]
                    Accessible.name: letter ? text : ["删除","完成搜索","取消搜索","切换大小写","空格","清空输入"][index-40]
                    contentItem: Item {
                        GridLayout {
                            anchors.centerIn: parent;columns: keyControl.index===41 || keyControl.index===42 ? 1 : 2;rowSpacing: keyboard.keyHeight*.14;columnSpacing: keyboard.keyHeight*.07
                            ControllerGlyph {
                                visible: !keyControl.letter
                                Layout.alignment: Qt.AlignCenter
                                Layout.preferredWidth: keyboard.keyHeight*.3;Layout.preferredHeight: keyboard.keyHeight*.3
                                button: ["X","Menu","B","R3","Y","LB"][keyControl.index-40] || "A"
                            }
                            ControllerGlyph { visible: keyControl.index===40;button: "delete";Layout.preferredWidth: keyboard.keyHeight*.34;Layout.preferredHeight: keyboard.keyHeight*.3 }
                            Label {
                                visible: keyControl.index!==40
                                Layout.alignment: Qt.AlignCenter
                                text: keyControl.index===43 && keyboard.upper ? "小写" : keyControl.text
                                color: Theme.text;font: keyControl.font
                            }
                        }
                    }
                    background: Rectangle {
                        radius: 0;color: keyControl.hovered ? Theme.hover : Theme.dark ? "#232527" : Theme.surface
                        border.width: keyboard.selectedKey===keyControl.index && !keyboard.candidates ? 3 : 1
                        border.color: keyboard.selectedKey===keyControl.index && !keyboard.candidates ? Qt.rgba(Theme.accent.r,Theme.accent.g,Theme.accent.b,.65) : Theme.border
                    }
                    onClicked: { keyboard.selectKey(index);keyboard.press(index) }
                }
            }
        }
    }
}
