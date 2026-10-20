import QtQuick
import QtQuick.Controls

AppComboBox {
    id: choice
    required property var navigationHost
    readonly property bool controllerSelectable: true
    readonly property var mapper: backend.mapping
    readonly property bool reverse: mapper.profile.mode==="keys_to_pad"
    implicitWidth: 145;currentIndex: -1
    model: mapper.allKeys;textRole: "label"
    displayText: reverse ? "选择输入键" : "选择键盘键"
    function activate() { controllerInput("activate") }
    onActivated: {
        if(currentIndex>=0) mapper.chooseKey(mapper.allKeys[currentIndex].token)
        currentIndex=-1
    }
    Connections {
        target: choice.popup
        function onVisibleChanged() {
            if(choice.popup.visible) choice.navigationHost.activeBindingChoice=choice
            else if(choice.navigationHost.activeBindingChoice===choice) choice.navigationHost.activeBindingChoice=null
        }
    }
    ToolTip.visible: hovered && !backend.controllerMode
    ToolTip.text: reverse ? "选择当前绑定的键盘输入" : "选中后加入当前组合，再选同一键可移除"
}
