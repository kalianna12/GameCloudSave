import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: personal; width: 820; height: 720; minimumWidth: 540; minimumHeight: 480
    title: "个性化"; color: Theme.background; font.family: "Microsoft YaHei UI"
    Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    function openPersonalization() { customUrl.text=backend.settings.custom_cover_url;show();raise();requestActivate() }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: personal.width<640 ? 20 : 28; spacing: 18
        RowLayout {
            Layout.fillWidth: true
            Label { text: "个性化"; font.pixelSize: 28; font.weight: Font.DemiBold; color: Theme.text }
            Item { Layout.fillWidth: true }
            AppButton { text: "关闭"; onClicked: personal.close() }
        }
        ScrollView {
            id: scroll; objectName: "personalizationScroll"; Layout.fillWidth: true; Layout.fillHeight: true
            clip: true; rightPadding: 16; contentWidth: availableWidth
            ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
            ScrollBar.vertical: ScrollBar {
                parent: scroll; anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.right: parent.right
                objectName: "personalizationBar"; orientation: Qt.Vertical; policy: ScrollBar.AlwaysOn; active: true; width: 8
                contentItem: Rectangle { implicitWidth: 6; implicitHeight: 24; radius: 3; color: parent.pressed ? Theme.accent : Theme.secondary; opacity: .7 }
                background: Rectangle { color: Theme.surface; radius: 3 }
            }
            ColumnLayout {
                width: scroll.availableWidth; spacing: 20
                Label { text: "游戏库设计"; font.pixelSize: 18; font.weight: Font.DemiBold; color: Theme.text }
                GridLayout {
                    Layout.fillWidth: true; columns: personal.width<700 ? 1 : 2; columnSpacing: 12; rowSpacing: 12
                    Repeater {
                        model: backend.libraryDesigns
                        LibraryDesignChoice {
                            required property var modelData
                            objectName: "design-"+modelData.id; design: modelData
                            Layout.fillWidth: true; Layout.preferredHeight: 170
                            enabled: !backend.busy; selected: (backend.settings.library_design || "classic")===modelData.id
                            onClicked: backend.saveSettings(modelData.id==="classic" ? {library_design:"classic"} : {library_design:modelData.id,theme:modelData.theme,accent_color:""})
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    AppButton { id: colorsToggle; objectName: "colorThemesToggle"; text: "调整配色"; flat: true; checkable: true }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "导入配色"; flat: true; enabled: !backend.busy; onClicked: backend.importTheme() }
                }
                GridLayout {
                    id: themeGrid; objectName: "themeGrid"; Layout.fillWidth: true; visible: colorsToggle.checked
                    columns: Math.max(2,Math.floor(width/180)); columnSpacing: 12; rowSpacing: 12
                    Repeater {
                        model: backend.themePresets
                        ThemeChoice {
                            required property var modelData
                            objectName: "theme-"+modelData.id; colors: modelData
                            Layout.fillWidth: true; Layout.minimumWidth: 120; Layout.preferredHeight: 120
                            enabled: !backend.busy; selected: backend.settings.theme===modelData.id
                            onClicked: backend.saveSettings({theme:modelData.id,accent_color:""})
                        }
                    }
                }
                Label { text: "强调色"; font.pixelSize: 18; font.weight: Font.DemiBold; color: Theme.text }
                Flow {
                    Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: 12
                    Repeater {
                        model: ["#80c942","#72b7ec","#b59de3","#edb96c","#eb8598"]
                        AbstractButton {
                            required property string modelData
                            width: 38; height: 38; enabled: !backend.busy; Accessible.name: "强调色 "+modelData
                            background: Rectangle { radius: 19; color: modelData; border.width: 3; border.color: backend.settings.accent_color===modelData ? Theme.text : "transparent" }
                            onClicked: backend.saveSettings({accent_color:modelData})
                        }
                    }
                    AppButton { text: "跟随主题"; enabled: !backend.busy; onClicked: backend.saveSettings({accent_color:""}) }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    CheckBox { text: "界面动效"; checked: backend.settings.animations; enabled: !backend.busy; onToggled: backend.saveSettings({animations:checked}) }
                    CheckBox { text: "手柄导航"; checked: backend.settings.gamepad_enabled; enabled: !backend.busy; onToggled: backend.saveSettings({gamepad_enabled:checked}) }
                    CheckBox { text: "导航提示音"; checked: backend.settings.navigation_sounds; enabled: !backend.busy; onToggled: backend.saveSettings({navigation_sounds:checked}) }
                    CheckBox { text: "自动备份通知"; checked: backend.settings.tray_notifications; enabled: !backend.busy; onToggled: backend.saveSettings({tray_notifications:checked}) }
                }
                AppButton { id: advanced; objectName: "customCoverToggle"; text: "自定义封面来源"; flat: true; checkable: true }
                ColumnLayout {
                    visible: advanced.checked; Layout.fillWidth: true; spacing: 10
                    AppTextField { id: customUrl; objectName: "customCoverUrl"; Layout.fillWidth: true; placeholderText: "搜索地址（包含 {query}）" }
                    AppButton { objectName: "saveCoverSource"; text: "保存来源"; enabled: !backend.busy; onClicked: backend.saveSettings({custom_cover_url:customUrl.text}) }
                }
            }
        }
        Label { text: backend.status; color: Theme.secondary; Layout.fillWidth: true; elide: Text.ElideRight; font.pixelSize: 12 }
    }
}
