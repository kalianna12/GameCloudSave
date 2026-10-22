import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ControllerForm.js" as Form
Dialog {
    id: dialog
    objectName: "restoreDialog"
    property string ident: ""
    property string mappingId: ""
    readonly property var preview: backend.restorePreview.ident===ident ? backend.restorePreview : ({})
    onPreviewChanged: if(preview.snapshot && mapAccount && mappingId!==preview.ident+":"+preview.snapshot) {
        mappingId=preview.ident+":"+preview.snapshot
        mapAccount.checked=!!preview.needs_mapping
        sourceAccount.currentIndex=0;targetAccount.currentIndex=0
    }
    width: Math.min(660,parent ? parent.width-60 : 660)
    modal: true
    exit: Transition {}
    title: "恢复存档"
    onOpened: cancelRestore.forceActiveFocus()
    function begin(gameId,snapshot,record) {
        ident=gameId;mappingId="";slotChoice.currentIndex=0;sourceAccount.currentIndex=0;targetAccount.currentIndex=0
        backend.previewRestore(gameId,snapshot,record);open()
    }
    function controllerInput(command) {
        if(command==="back") { close();return true }
        if(command==="activate") {
            var focus=dialog.contentItem.Window.window.activeFocusItem
            if(focus===confirmRestore) { acceptRestore();return true }
            if(focus===cancelRestore) { close();return true }
        }
        return Form.handle([slotChoice,mapAccount,sourceAccount,targetAccount,cancelRestore,confirmRestore],dialog.contentItem.Window.window.activeFocusItem,command,null)
    }
    function acceptRestore() {
        if(!confirmRestore.enabled) return
        backend.restoreWithOptions(dialog.ident,dialog.preview.snapshot,{slot:slotChoice.currentIndex>0 ? slotChoice.currentText : "",source_account:mapAccount.checked ? sourceAccount.currentText : "",target_account:mapAccount.checked ? targetAccount.currentText : ""})
        close()
    }
    Overlay.modal: Rectangle { color: "#bb000000" }
    contentItem: ColumnLayout {
        spacing: 14
        Label { text: backend.busy ? "正在读取备份…" : dialog.preview.snapshot ? "备份包含 "+dialog.preview.file_count+" 个文件" : backend.status; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Label { text: "目标："+(dialog.preview.target || ""); visible: !!dialog.preview.target; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        AppComboBox { id: slotChoice; objectName: "restoreSlotChoice"; Layout.fillWidth: true; model: ["全部存档"].concat(dialog.preview.slots || []); visible: (dialog.preview.slots || []).length>0 }
        CheckBox { id: mapAccount; objectName: "restoreMapAccount"; visible: (dialog.preview.source_accounts || []).length>0 && (dialog.preview.target_accounts || []).length>0; text: "恢复到本机账号"; checked: !!dialog.preview.needs_mapping; enabled: !dialog.preview.needs_mapping }
        RowLayout {
            visible: mapAccount.visible && mapAccount.checked; Layout.fillWidth: true
            AppComboBox { id: sourceAccount; objectName: "restoreSourceAccount"; Layout.fillWidth: true; model: ["选择备份账号"].concat(dialog.preview.source_accounts || []) }
            Label { text: "→" }
            AppComboBox { id: targetAccount; objectName: "restoreTargetAccount"; Layout.fillWidth: true; model: ["选择本机账号"].concat(dialog.preview.target_accounts || []) }
        }
        Label { text: "其他存档槽和账号保留；恢复前会备份当前目录。"; visible: slotChoice.currentIndex>0 || mapAccount.checked; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Label { text: "恢复前会备份当前目录。"; visible: slotChoice.currentIndex===0 && !mapAccount.checked; color: Theme.secondary }
    }
    footer: DialogButtonBox {
        AppButton { id: cancelRestore;objectName: "cancelRestore";text: "取消"; DialogButtonBox.buttonRole: DialogButtonBox.RejectRole }
        AppButton {
            id: confirmRestore;objectName: "confirmRestore"; text: "恢复所选存档"; highlighted: true; DialogButtonBox.buttonRole: DialogButtonBox.AcceptRole
            enabled: !backend.busy && !!dialog.preview.snapshot && (!mapAccount.checked || sourceAccount.currentIndex>0 && targetAccount.currentIndex>0)
        }
        onRejected: dialog.close()
        onAccepted: dialog.acceptRestore()
    }
}
