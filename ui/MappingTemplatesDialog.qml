import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    objectName: "mappingTemplatesDialog"
    modal: true;title: "手柄到键鼠模板";padding: 20
    width: Math.min(1120,parent ? parent.width-48 : 1120)
    height: Math.min(800,parent ? parent.height-48 : 800)
    anchors.centerIn: parent
    readonly property var mapper: backend.mapping
    readonly property var catalog: mapper.templates
    property int selection: 0
    property string error: ""
    readonly property var entry: catalog[selection] || ({name:"",summary:"",note:"",bindings:[]})
    component Action: AppButton { readonly property bool controllerSelectable: true }
    onOpened: error=""
    Overlay.modal: Rectangle { color: "#66000000" }
    enter: Transition { NumberAnimation { property: "opacity";from: 0;to: 1;duration: Theme.motion ? 100 : 0 } }
    exit: Transition { NumberAnimation { property: "opacity";from: 1;to: 0;duration: Theme.motion ? 80 : 0 } }
    background: Rectangle { color: Theme.background;radius: 16;border.color: Theme.outline }
    contentItem: RowLayout {
        spacing: 24
        ListView {
            objectName: "mappingTemplateList"
            Layout.preferredWidth: 232;Layout.fillHeight: true;clip: true;spacing: 6
            model: dialog.catalog
            ScrollBar.vertical: ScrollBar {}
            delegate: ItemDelegate {
                required property var modelData
                required property int index
                objectName: "mappingTemplate-"+modelData.id
                readonly property bool controllerSelectable: true
                width: ListView.view.width;height: 54;hoverEnabled: !backend.controllerMode
                onClicked: dialog.selection=index
                onActiveFocusChanged: if(activeFocus) dialog.selection=index
                function activate() { dialog.selection=index }
                contentItem: Text { text: modelData.name.slice(5);color: dialog.selection===index ? Theme.accent : Theme.text;font.pixelSize: 13;wrapMode: Text.Wrap;verticalAlignment: Text.AlignVCenter }
                background: Rectangle { radius: 8;color: dialog.selection===index ? Theme.hover : "transparent";border.color: dialog.selection===index ? Theme.accent : "transparent" }
            }
        }
        Rectangle { Layout.fillHeight: true;width: 1;color: Theme.outline }
        ColumnLayout {
            Layout.fillWidth: true;Layout.fillHeight: true;spacing: 12
            Label { objectName: "mappingTemplateTitle";Layout.fillWidth: true;text: dialog.entry.name;color: Theme.text;font.pixelSize: 21;font.weight: Font.DemiBold;wrapMode: Text.Wrap }
            Label { Layout.fillWidth: true;text: dialog.entry.summary;color: Theme.secondary;font.pixelSize: 13;wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "输入";Layout.preferredWidth: 86;color: Theme.secondary;font.pixelSize: 12 }
                Label { text: "输出";Layout.preferredWidth: 150;color: Theme.secondary;font.pixelSize: 12 }
                Label { text: "用途";Layout.fillWidth: true;color: Theme.secondary;font.pixelSize: 12 }
            }
            ListView {
                objectName: "mappingTemplateBindings";Layout.fillWidth: true;Layout.fillHeight: true;clip: true;model: dialog.entry.bindings
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AlwaysOn }
                delegate: Item {
                    required property var modelData
                    required property int index
                    objectName: "mappingTemplateBinding-"+index
                    width: ListView.view.width;height: Math.max(34,actionText.implicitHeight+12,outputText.implicitHeight+12)
                    Rectangle { anchors.bottom: parent.bottom;width: parent.width;height: 1;color: Theme.outline;opacity: .35 }
                    RowLayout {
                        anchors.fill: parent;anchors.rightMargin: 14;spacing: 6
                        Label { text: modelData.input;Layout.preferredWidth: 86;color: Theme.text;font.pixelSize: 13 }
                        Label { id: outputText;text: modelData.output;Layout.preferredWidth: 150;color: Theme.accent;font.pixelSize: 13;wrapMode: Text.Wrap }
                        Label { id: actionText;text: modelData.action;Layout.fillWidth: true;color: Theme.secondary;font.pixelSize: 13;wrapMode: Text.Wrap }
                    }
                }
            }
            Label { Layout.fillWidth: true;text: dialog.entry.note;color: Theme.secondary;font.pixelSize: 12;wrapMode: Text.Wrap }
        }
    }
    footer: ColumnLayout {
        spacing: 10
        Label { visible: !!dialog.error;Layout.fillWidth: true;Layout.leftMargin: 20;Layout.rightMargin: 20;text: dialog.error;color: Theme.accent;wrapMode: Text.Wrap }
        RowLayout {
            Layout.fillWidth: true;Layout.margins: 20;spacing: 10
            Action { objectName: "mappingAddAllTemplates";text: "添加全部 8 组";onClicked: { if(dialog.mapper.addAllTemplates()) dialog.close();else dialog.error=dialog.mapper.state.message } ToolTip.visible: hovered && !backend.controllerMode;ToolTip.text: "已添加的模板保持不变" }
            Item { Layout.fillWidth: true }
            Action { objectName: "mappingAddTemplate";text: dialog.mapper.addedTemplates.indexOf(dialog.entry.id)>=0 ? "打开配置" : "创建并编辑";highlighted: true;onClicked: { if(dialog.mapper.addTemplate(dialog.entry.id)) dialog.close();else dialog.error=dialog.mapper.state.message } }
            Action { objectName: "mappingTemplateClose";text: "关闭";onClicked: dialog.close() }
        }
    }
}
