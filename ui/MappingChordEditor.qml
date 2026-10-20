import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
    id: editor
    property bool source: false
    readonly property var mapper: backend.mapping
    readonly property var values: source ? mapper.sourceChord : mapper.currentChord
    readonly property string text: values.map(function(t) { return mapper.label(t) }).join(" + ") || "未绑定"
    property string editingToken: ""
    property point anchorPoint: Qt.point(0,0)
    property real anchorHeight: 32
    implicitHeight: Math.max(32,tokens.implicitHeight)
    enabled: !mapper.state.recording
    function openToken(token,item) {
        editingToken=token
        anchorPoint=item.mapToItem(Overlay.overlay,0,0);anchorHeight=item.height
        filter.text="";picker.options=mapper.chordOptions(editor.source)
        picker.open()
    }
    Connections {
        target: editor.mapper
        function onSelectionChanged() { picker.close() }
    }
    Flow {
        id: tokens;width: parent.width;spacing: 6
        Repeater {
            model: editor.values
            Row {
                id: member
                required property string modelData
                required property int index
                spacing: 6
                Label { visible: member.index>0;text: "+";color: Theme.secondary;height: 32;verticalAlignment: Text.AlignVCenter }
                Rectangle {
                    id: chip;height: 32;width: Math.min(Math.max(58,keyName.implicitWidth+42),Math.max(58,tokens.width-20))
                    radius: 6;color: editMouse.containsMouse || removeMouse.containsMouse ? Theme.hover : Theme.background
                    border.width: 1;border.color: editMouse.containsMouse || removeMouse.containsMouse ? Theme.accent : Theme.outline
                    Label {
                        id: keyName;anchors.left: parent.left;anchors.leftMargin: 10;anchors.right: parent.right;anchors.rightMargin: 28;anchors.verticalCenter: parent.verticalCenter
                        text: editor.mapper.label(member.modelData);color: Theme.accent;font.pixelSize: 14;elide: Text.ElideRight
                    }
                    MouseArea {
                        id: editMouse;objectName: editor.objectName+"-edit-"+member.modelData
                        anchors.fill: parent;anchors.rightMargin: 26;hoverEnabled: true;cursorShape: Qt.PointingHandCursor
                        onClicked: editor.openToken(member.modelData,chip)
                    }
                    Label { anchors.right: parent.right;width: 26;height: parent.height;text: "×";font.pixelSize: 18;color: removeMouse.containsMouse ? Theme.text : Theme.secondary;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter }
                    MouseArea {
                        id: removeMouse;objectName: editor.objectName+"-remove-"+member.modelData
                        anchors.right: parent.right;width: 26;height: parent.height;hoverEnabled: true;cursorShape: Qt.PointingHandCursor
                        onClicked: editor.mapper.editChordToken(member.modelData,"",editor.source)
                    }
                    ToolTip.visible: !picker.visible && (editMouse.containsMouse || removeMouse.containsMouse)
                    ToolTip.delay: 450
                    ToolTip.text: (removeMouse.containsMouse ? "删除 " : "替换 ")+editor.mapper.label(member.modelData)
                }
            }
        }
        Label { visible: !editor.values.length;text: editor.source ? "点击上方键盘或鼠标选择输入" : "未绑定";color: Theme.secondary;height: 32;verticalAlignment: Text.AlignVCenter }
    }
    Popup {
        id: picker;objectName: editor.objectName+"-picker";parent: Overlay.overlay
        property var options: []
        width: Math.min(320,parent.width-32);height: Math.min(360,parent.height-32)
        x: Math.max(16,Math.min(editor.anchorPoint.x,parent.width-width-16))
        y: Math.max(16,Math.min(editor.anchorPoint.y+editor.anchorHeight+6,parent.height-height-16))
        modal: true;focus: true;padding: 14;closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        Overlay.modal: Rectangle { color: "#66000000" }
        enter: Transition {}
        exit: Transition {}
        background: Rectangle { radius: Theme.radius;color: Theme.surface;border.color: Theme.border }
        contentItem: ColumnLayout {
            spacing: 10
            Label { text: "替换 "+editor.mapper.label(editor.editingToken);color: Theme.text;font.pixelSize: 16;font.bold: true }
            AppTextField { id: filter;objectName: editor.objectName+"-filter";Layout.fillWidth: true;placeholderText: "搜索按键" }
            ListView {
                id: choices;objectName: editor.objectName+"-choices";Layout.fillWidth: true;Layout.fillHeight: true;clip: true
                model: picker.options.filter(function(option) { return !filter.text || (option.label+" "+option.token).toLowerCase().indexOf(filter.text.toLowerCase())>=0 })
                ScrollBar.vertical: ScrollBar {}
                delegate: ItemDelegate {
                    required property var modelData
                    objectName: editor.objectName+"-option-"+modelData.token
                    width: choices.width;height: 36;text: modelData.label;highlighted: modelData.token===editor.editingToken
                    onClicked: { var old=editor.editingToken,value=modelData.token;picker.close();editor.mapper.editChordToken(old,value,editor.source) }
                    contentItem: Label { text: parent.text;color: Theme.text;verticalAlignment: Text.AlignVCenter }
                    background: Rectangle { radius: 4;color: parent.hovered || parent.highlighted ? Theme.hover : "transparent" }
                }
                Label { anchors.centerIn: parent;visible: !choices.count;text: "没有匹配的按键";color: Theme.secondary }
            }
            AppButton { objectName: editor.objectName+"-delete";Layout.fillWidth: true;text: "删除此键";onClicked: { var old=editor.editingToken;picker.close();editor.mapper.editChordToken(old,"",editor.source) } }
        }
    }
}
