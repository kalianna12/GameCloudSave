import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: keyboard
    title: "搜索游戏"
    modal: true; focus: true; closePolicy: Popup.NoAutoClose
    Overlay.modal: Rectangle { color: "#bb000000" }
    property string value: ""
    property bool words: false
    property bool upper: false
    property int page: 0
    property int selectedKey: 0
    property var quickTerms: []
    readonly property var pageTerms: quickTerms.slice(page*20,(page+1)*20)
    readonly property var keyLabels: (words ? pageTerms : (upper ? "1234567890QWERTYUIOPASDFGHJKL-ZXCVBNM,.#" : "1234567890qwertyuiopasdfghjkl-zxcvbnm,.#").split("")).concat(["空格","删除","清空",words ? "字母" : "中文",words ? "下一页" : "大小写","完成"])
    signal submitted(string value)
    signal cancelled()
    onKeyLabelsChanged: selectedKey=Math.max(0,Math.min(selectedKey,keyLabels.length-1))
    function start(text) { value=text;words=false;page=0;selectedKey=0;open() }
    function finish() { submitted(value);close() }
    function press(index) {
        var label=keyLabels[index]
        if(label==="完成") finish()
        else if(label==="删除") value=value.slice(0,-1)
        else if(label==="清空") value=""
        else if(label==="空格") value+=" "
        else if(label==="大小写") upper=!upper
        else if(label==="下一页") { page=(page+1)%Math.max(1,Math.ceil(quickTerms.length/20));selectedKey=0 }
        else if(label==="字母" || label==="中文") { words=!words;page=0;selectedKey=0 }
        else if(words) value=label
        else value+=label
    }
    function controllerInput(command) {
        if(!visible) return false
        var previous=selectedKey,columns=words ? 4 : 10
        if(command==="back") { close();cancelled() }
        else if(command==="activate") press(selectedKey)
        else if(command==="favorite") value=value.slice(0,-1)
        else if(command==="history") { words=!words;page=0;selectedKey=0 }
        else if(command==="launch") finish()
        else if(command==="left" || command==="previous") selectedKey=Math.max(0,selectedKey-1)
        else if(command==="right" || command==="next") selectedKey=Math.min(keyLabels.length-1,selectedKey+1)
        else if(command==="up") selectedKey=Math.max(0,selectedKey-columns)
        else if(command==="down") selectedKey=Math.min(keyLabels.length-1,selectedKey+columns)
        if(previous!==selectedKey) backend.navigationMoved()
        return true
    }
    contentItem: ColumnLayout {
        spacing: 12
        Label { objectName: "keyboardValue"; text: keyboard.value || "输入名称，或按 Y 选择中文名称、标签和系列"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 20; color: Theme.text }
        Label { visible: keyboard.words && keyboard.selectedKey<keyboard.pageTerms.length; text: keyboard.keyLabels[keyboard.selectedKey] || ""; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        GridLayout {
            Layout.fillWidth: true; columns: keyboard.words ? 4 : 10; rowSpacing: 6; columnSpacing: 6
            Repeater {
                model: keyboard.keyLabels
                AppButton {
                    required property string modelData
                    required property int index
                    objectName: "keyboardKey-"+index
                    text: modelData; Layout.fillWidth: true; Layout.minimumWidth: 0
                    highlighted: index===keyboard.selectedKey; implicitHeight: keyboard.words ? 48 : 42
                    onClicked: { keyboard.selectedKey=index;keyboard.press(index) }
                    ToolTip.visible: hovered; ToolTip.text: text
                }
            }
        }
        Label { text: "方向键 / 左摇杆移动 · A 输入 · X 删除 · Y 中文词条 / 字母 · Menu 搜索 · B 取消"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
    }
}
