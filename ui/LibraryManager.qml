import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: manager; width: 1220; height: 800; minimumWidth: 1020; minimumHeight: 650
    title: "分类与系列"; color: Theme.background; font.family: "Microsoft YaHei UI"; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    property var selected: ({})
    property var edits: ({})
    function openManager() { edits=({});selected=({});show();raise();requestActivate();backend.previewOrganizer(false) }
    function update(id,field,value) { var next=Object.assign({},edits);var row=Object.assign({},next[id] || {});row[field]=value;next[id]=row;edits=next }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "分类与系列"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: manager.close() } }
        RowLayout {
            AppTextField { id: groupName; placeholderText: "新分类名称"; Layout.fillWidth: true; maximumLength: 32 }
            AppButton { text: "创建分类"; enabled: !backend.busy && !!groupName.text.trim(); onClicked: backend.editGroup("",groupName.text) }
            ComboBox { id: group; model: backend.groups; Layout.preferredWidth: 180 }
            AppButton { text: "重命名"; enabled: !backend.busy && !!group.currentText && !!groupName.text.trim(); onClicked: backend.editGroup(group.currentText,groupName.text) }
            AppButton { text: "删除分类"; enabled: !backend.busy && !!group.currentText; onClicked: deleteGroup.open() }
        }
        RowLayout {
            AppButton { text: "规则建议"; enabled: !backend.busy; onClicked: { manager.edits=({});backend.previewOrganizer(false) } }
            AppButton { text: "AI 智能分组"; enabled: !backend.busy && backend.settings.has_ai_key; onClicked: { manager.edits=({});backend.previewOrganizer(true) } }
            AppButton { text: "全选"; enabled: !backend.busy; onClicked: { var next={};backend.organizerResults.forEach(function(row) { next[row.id]=true });manager.selected=next } }
            AppButton { text: "清除选择"; onClicked: manager.selected=({}) }
            Item { Layout.fillWidth: true }
            AppButton { text: "应用所选分类"; highlighted: true; enabled: !backend.busy && Object.keys(manager.selected).length>0; onClicked: {
                var rows=backend.organizerResults.filter(function(row) { return manager.selected[row.id] }).map(function(row) { var edit=manager.edits[row.id] || {};return {id:row.id,category:edit.category || row.category,tags:edit.tags!==undefined ? edit.tags.split(/[,，]/).map(function(name) { return name.trim() }).filter(Boolean) : row.tags,series:edit.series!==undefined ? edit.series : row.series} });backend.updateLibrary(rows)
            } }
        }
        Label { text: "主分类选一个，标签可填写多个。系列至少包含两款游戏才在主页展示。建议可编辑，应用后生效。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        ListView { id: list; Layout.fillWidth: true; Layout.fillHeight: true; model: backend.organizerResults; clip: true; spacing: 3
            delegate: ItemDelegate { required property var modelData; width: ListView.view.width; height: 78
                contentItem: RowLayout {
                    CheckBox { checked: !!manager.selected[modelData.id]; onToggled: { var next=Object.assign({},manager.selected);if(checked) next[modelData.id]=true;else delete next[modelData.id];manager.selected=next } }
                    Label { text: modelData.name; Layout.preferredWidth: 250; Layout.minimumWidth: 180; elide: Text.ElideRight; font.bold: true }
                    ComboBox { Layout.preferredWidth: 148; model: backend.primaryCategories.concat(backend.groups.filter(function(name) { return backend.primaryCategories.indexOf(name)<0 })); currentIndex: Math.max(0,model.indexOf((manager.edits[modelData.id] || {}).category || modelData.category)); onActivated: manager.update(modelData.id,"category",currentText) }
                    AppTextField { Layout.fillWidth: true; placeholderText: "标签，用逗号分隔"; text: (manager.edits[modelData.id] || {}).tags!==undefined ? manager.edits[modelData.id].tags : (modelData.tags || []).join(", "); onTextEdited: manager.update(modelData.id,"tags",text) }
                    AppTextField { Layout.preferredWidth: 190; placeholderText: "系列"; text: (manager.edits[modelData.id] || {}).series!==undefined ? manager.edits[modelData.id].series : modelData.series || ""; onTextEdited: manager.update(modelData.id,"series",text) }
                }
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Label { text: backend.status; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
    Dialog { id: deleteGroup; title: "删除分类"; modal: true; anchors.centerIn: parent; standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text: "移除分类及其关联，游戏和存档保留。" }
        onAccepted: backend.editGroup(group.currentText,"")
    }
}
