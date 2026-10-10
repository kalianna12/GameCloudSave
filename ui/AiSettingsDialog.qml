import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "enrichmentAiSettings"
    title: "DeepSeek 设置"; modal: true; focus: true
    width: Math.min(520,parent.width-48); anchors.centerIn: parent
    Overlay.modal: Rectangle { color: "#bb000000" }
    function openSettings() { model.text=backend.settings.ai_model;key.text="";open() }
    onClosed: key.text=""
    contentItem: ColumnLayout {
        spacing: 12
        Label { text: "用于辅助匹配游戏名称，以及补充缺失的分类、标签和系列。发行日期仍由资料库提供。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        Label { text: "模型" }
        AppTextField { id: model; Layout.fillWidth: true }
        Label { text: "API Key" }
        AppTextField { id: key; objectName: "enrichmentAiKey"; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "已保存，留空保持" : "填写 DeepSeek API Key" }
        Label { text: backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        RowLayout {
            BusyIndicator { visible: backend.busy; running: visible; implicitWidth: 24; implicitHeight: 24 }
            AppButton { text: "保存并测试连接"; highlighted: true; enabled: !backend.busy && !!model.text && (!!key.text || backend.settings.has_ai_key); onClicked: backend.testAi({ai_enabled:true,ai_model:model.text,ai_key:key.text}) }
        }
    }
    standardButtons: Dialog.Close
}
