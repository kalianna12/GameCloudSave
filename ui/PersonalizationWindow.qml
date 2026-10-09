import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: personal; width: 820; height: 680; minimumWidth: 720; minimumHeight: 580
    title: "个性化"; color: Theme.background; font.family: "Microsoft YaHei UI"; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    function openPersonalization() { customUrl.text=backend.settings.custom_cover_url;show();raise();requestActivate() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 28; spacing: 20
        RowLayout { Label { text: "个性化"; font.pixelSize: 28; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: personal.close() } }
        Label { text: "主题"; font.pixelSize: 18; font.bold: true }
        RowLayout {
            Repeater { model: [{id:"dark",name:"碳灰",color:"#202326"},{id:"light",name:"浅色",color:"#e5e9ee"},{id:"midnight",name:"午夜蓝",color:"#18263a"},{id:"violet",name:"深紫",color:"#292333"}]
                AppButton { required property var modelData; text: modelData.name; enabled: !backend.busy; highlighted: backend.settings.theme===modelData.id; onClicked: backend.saveSettings({theme:modelData.id,accent_color:""}) }
            }
            AppButton { text: "导入主题 JSON"; enabled: !backend.busy; onClicked: backend.importTheme() }
        }
        Label { text: "强调色"; font.pixelSize: 18; font.bold: true }
        RowLayout { spacing: 16
            Repeater { model: ["#80c942","#72b7ec","#b59de3","#edb96c","#eb8598"]
                AbstractButton { required property string modelData; implicitWidth: 42; implicitHeight: 42; enabled: !backend.busy; Accessible.name: "强调色 "+modelData
                    background: Rectangle { radius: 21; color: modelData; border.width: 3; border.color: Theme.accent===modelData ? Theme.text : "transparent" }
                    onClicked: backend.saveSettings({accent_color:modelData})
                }
            }
            AppButton { text: "跟随主题"; onClicked: backend.saveSettings({accent_color:""}) }
        }
        CheckBox { text: "界面动效"; checked: backend.settings.animations; enabled: !backend.busy; onToggled: backend.saveSettings({animations:checked}) }
        CheckBox { text: "自动备份时显示托盘通知"; checked: backend.settings.tray_notifications; enabled: !backend.busy; onToggled: backend.saveSettings({tray_notifications:checked}) }
        Label { text: "自定义封面来源"; font.pixelSize: 18; font.bold: true }
        AppTextField { id: customUrl; Layout.fillWidth: true; placeholderText: "https://服务/search?q={query}" }
        Label { text: "GET 返回 items 数组，每项包含 id、name、image（图片 URL），page 可选。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        AppButton { text: "保存来源"; enabled: !backend.busy; onClicked: backend.saveSettings({custom_cover_url:customUrl.text}) }
        Item { Layout.fillHeight: true }
        Label { text: backend.status; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
