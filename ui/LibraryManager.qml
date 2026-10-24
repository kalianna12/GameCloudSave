import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    ControlFocus {}
    id: manager; width: 1220; height: 800; minimumWidth: 1020; minimumHeight: 650
    title: "分类与系列"; color: Theme.background; font.family: "Microsoft YaHei UI"; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    property var selected: ({})
    property var edits: ({})
    property var approved: ({})
    property var pendingIds: []
    property string pendingAction: ""
    property bool selectingDefaults: false
    function openManager() { edits=({});selected=({});approved=({});selectingDefaults=true;show();raise();requestActivate();backend.previewOrganizer(false) }
    function selectUnclassified() { var next={};backend.organizerResults.forEach(function(row) { if(!row.protected) next[row.id]=true });selected=next }
    function selectIds(ids) { var next=Object.assign({},selected);ids.forEach(function(id) { next[id]=true });selected=next }
    function warn(action,ids) { pendingAction=action;pendingIds=ids;overwriteWarning.open() }
    function choose(row,checked) {
        if(!checked) { var next=Object.assign({},selected);delete next[row.id];selected=next;return }
        if(row.protected && !approved[row.id]) warn("select",[row.id]);else selectIds([row.id])
    }
    function selectedRows() { return backend.organizerResults.filter(function(row) { return manager.selected[row.id] }) }
    function previewAi() {
        var rows=selectedRows();var ids=rows.map(function(row) { return row.id })
        if(!ids.length) return
        var existing=rows.filter(function(row) { return row.protected && !manager.approved[row.id] }).map(function(row) { return row.id })
        if(existing.length) warn("preview",existing);else backend.previewOrganizer(true,ids,rows.some(function(row) { return row.protected }))
    }
    function applySelected() {
        var source=selectedRows()
        var existing=source.filter(function(row) { return row.protected && !manager.approved[row.id] }).map(function(row) { return row.id })
        if(existing.length) { warn("apply",existing);return }
        var rows=source.map(function(row) { var edit=manager.edits[row.id] || {};return {id:row.id,category:edit.category || row.category,tags:edit.tags!==undefined ? edit.tags.split(/[,，]/).map(function(name) { return name.trim() }).filter(Boolean) : row.tags,tags_manual:edit.tags!==undefined,tags_source:edit.tags!==undefined ? "手动" : row.tags_source || "未记录",series:edit.series!==undefined ? edit.series : row.series} })
        backend.applyOrganizer(rows,source.some(function(row) { return row.protected }))
    }
    Connections { target: backend; function onOperationCompleted(action,success) {
        if(action==="organizer-preview" && manager.selectingDefaults) { manager.selectingDefaults=false;if(success) manager.selectUnclassified() }
        if(action==="classification-apply" && success && manager.visible) { manager.selected=({});manager.approved=({});manager.edits=({});backend.previewOrganizer(false) }
    } }
    function update(id,field,value) { var next=Object.assign({},edits);var row=Object.assign({},next[id] || {});row[field]=value;next[id]=row;edits=next }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "分类与系列"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: manager.close() } }
        RowLayout {
            AppTextField { id: groupName; placeholderText: "新分类名称"; Layout.fillWidth: true; maximumLength: 32 }
            AppButton { text: "创建分类"; enabled: !backend.busy && !!groupName.text.trim(); onClicked: backend.editGroup("",groupName.text) }
            AppComboBox { id: group; model: backend.groups; Layout.preferredWidth: 180 }
            AppButton { text: "重命名"; enabled: !backend.busy && !!group.currentText && !!groupName.text.trim(); onClicked: backend.editGroup(group.currentText,groupName.text) }
            AppButton { text: "删除分类"; enabled: !backend.busy && !!group.currentText; onClicked: deleteGroup.open() }
        }
        RowLayout {
            AppButton { text: "规则建议"; enabled: !backend.busy; onClicked: { manager.edits=({});backend.previewOrganizer(false) } }
            AppButton { text: "DeepSeek 建议"; enabled: !backend.busy && backend.settings.has_ai_key && Object.keys(manager.selected).length>0; onClicked: { manager.edits=({});manager.previewAi() } }
            AppButton { objectName: "selectUnclassified"; text: "全选未分类"; enabled: !backend.busy; onClicked: manager.selectUnclassified() }
            AppButton { text: "选择全部…"; enabled: !backend.busy; onClicked: {
                var existing=backend.organizerResults.filter(function(row) { return row.protected && !manager.approved[row.id] }).map(function(row) { return row.id })
                if(existing.length) manager.warn("all",existing);else manager.selectIds(backend.organizerResults.map(function(row) { return row.id }))
            } }
            AppButton { text: "清除选择"; onClicked: manager.selected=({}) }
            Item { Layout.fillWidth: true }
            AppButton { text: "应用所选分类"; highlighted: true; enabled: !backend.busy && Object.keys(manager.selected).length>0; onClicked: manager.applySelected() }
        }
        Label { text: "建议仅补缺失内容，应用前可修改。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        ListView { id: list; Layout.fillWidth: true; Layout.fillHeight: true; model: backend.organizerResults; clip: true; spacing: 3
            delegate: ItemDelegate { required property var modelData; width: ListView.view.width; height: 78
                contentItem: RowLayout {
                    CheckBox { checked: !!manager.selected[modelData.id]; onToggled: manager.choose(modelData,checked) }
                    ColumnLayout { Layout.preferredWidth: 250; Layout.minimumWidth: 180; spacing: 3
                        Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                        Label { text: (modelData.protected ? "已分类" : "未分类")+" · 标签来源："+(modelData.tags_source || "未记录"); Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary; font.pixelSize: 11 }
                    }
                    AppComboBox { enabled: !modelData.protected || !!manager.selected[modelData.id]; Layout.preferredWidth: 148; model: backend.primaryCategories.concat(backend.groups.filter(function(name) { return backend.primaryCategories.indexOf(name)<0 })); currentIndex: Math.max(0,model.indexOf((manager.edits[modelData.id] || {}).category || modelData.category)); onActivated: manager.update(modelData.id,"category",currentText) }
                    AppTextField { enabled: !modelData.protected || !!manager.selected[modelData.id]; Layout.fillWidth: true; placeholderText: "标签，用逗号分隔"; text: (manager.edits[modelData.id] || {}).tags!==undefined ? manager.edits[modelData.id].tags : (modelData.tags || []).join(", "); onTextEdited: manager.update(modelData.id,"tags",text) }
                    AppTextField { enabled: !modelData.protected || !!manager.selected[modelData.id]; Layout.preferredWidth: 190; placeholderText: "系列"; text: (manager.edits[modelData.id] || {}).series!==undefined ? manager.edits[modelData.id].series : modelData.series || ""; onTextEdited: manager.update(modelData.id,"series",text) }
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
    Dialog { id: overwriteWarning; objectName: "classificationWarning"; title: "重新分类已有游戏？"; modal: true; focus: true; anchors.centerIn: parent; width: 440; standardButtons: Dialog.Yes | Dialog.No
        onOpened: standardButton(Dialog.No).forceActiveFocus()
        Label { text: "所选 "+manager.pendingIds.length+" 款游戏已有分类、标签或系列。继续后可修改这些内容，是否继续？"; wrapMode: Text.Wrap }
        onAccepted: {
            var next=Object.assign({},manager.approved);manager.pendingIds.forEach(function(id) { next[id]=true });manager.approved=next
            if(manager.pendingAction==="select") manager.selectIds(manager.pendingIds)
            else if(manager.pendingAction==="all") manager.selectIds(backend.organizerResults.map(function(row) { return row.id }))
            else if(manager.pendingAction==="preview") manager.previewAi()
            else if(manager.pendingAction==="apply") manager.applySelected()
        }
        onRejected: manager.selected=Object.assign({},manager.selected)
        onClosed: manager.selected=Object.assign({},manager.selected)
    }
}
