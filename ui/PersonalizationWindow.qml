import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: personal; width: 820; height: 720; minimumWidth: 540; minimumHeight: 480
    title: "个性化"; color: Theme.background; font.family: "Microsoft YaHei UI"
    Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    component PadCheckBox: CheckBox {
        property bool controllerSelectable: true
        SelectionFrame { selected: parent.activeFocus; radius: 5 }
    }
    signal returnRequested()
    onClosing: returnRequested()
    function choices() {
        var result=[]
        function visit(item) { if(!item.visible) return;if(item.controllerSelectable && item.enabled) result.push(item);for(var i=0;i<item.children.length;i++) visit(item.children[i]) }
        visit(contentItem);return result
    }
    function focusChoice(target) {
        if(!target) return
        target.forceActiveFocus()
        var owner=target.parent
        while(owner && owner!==scroll) owner=owner.parent
        if(owner===scroll) {
            var view=scroll.contentItem,p=target.mapToItem(view,0,0)
            if(p.y<8) view.contentY=Math.max(0,view.contentY+p.y-8)
            else if(p.y+target.height>view.height-8) view.contentY=Math.min(Math.max(0,view.contentHeight-view.height),view.contentY+p.y+target.height-view.height+8)
        }
    }
    function focusDesign() { var list=choices(),selected=list.find(function(c) { return c.design && c.selected });focusChoice(selected || list[1] || list[0]) }
    function controllerInput(command) {
        if(command==="back") { close();return true }
        var list=choices(),current=activeFocusItem
        while(current && list.indexOf(current)<0) current=current.parent
        if(!current) { focusDesign();return true }
        if(command==="activate") {
            if(current.checkable) { current.toggle();current.toggled() }
            current.clicked();return true
        }
        if(["up","down","left","right"].indexOf(command)<0) return true
        var origin=current.mapToItem(contentItem,current.width/2,current.height/2),best=null,cost=Infinity
        list.forEach(function(candidate) {
            if(candidate===current) return
            var p=candidate.mapToItem(contentItem,candidate.width/2,candidate.height/2),dx=p.x-origin.x,dy=p.y-origin.y
            var forward=command==="left" ? -dx : command==="right" ? dx : command==="up" ? -dy : dy
            var cross=command==="left" || command==="right" ? Math.abs(dy) : Math.abs(dx)
            if(forward<=1 || (command==="left" || command==="right") && cross>(candidate.height+current.height)/2) return
            var score=forward+cross*(command==="left" || command==="right" ? 2 : .35);if(score<cost) { cost=score;best=candidate }
        })
        if(best) { focusChoice(best);backend.navigationMoved() }
        return true
    }
    function openPersonalization() { customUrl.text=backend.settings.custom_cover_url;show();raise();requestActivate();if(backend.controllerMode) Qt.callLater(focusDesign) }
    ColumnLayout {
        x: personal.width<640 ? 20 : 28; y: x
        width: Math.max(0,personal.width-x*2); height: Math.max(0,personal.height-y*2); spacing: 18
        RowLayout {
            Layout.fillWidth: true
            Label { text: "个性化"; font.pixelSize: 28; font.weight: Font.DemiBold; color: Theme.text }
            Item { Layout.fillWidth: true }
            AppButton { property bool controllerSelectable: true; objectName: "personalClose"; text: "关闭"; onClicked: personal.close() }
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
                            property bool controllerSelectable: true
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
                    AppButton { id: colorsToggle; property bool controllerSelectable: true; objectName: "colorThemesToggle"; text: "调整配色"; flat: true; checkable: true }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "导入配色"; flat: true; enabled: !backend.busy; onClicked: backend.importTheme() }
                }
                GridLayout {
                    id: themeGrid; objectName: "themeGrid"; Layout.fillWidth: true; visible: colorsToggle.checked
                    columns: Math.max(2,Math.floor(width/180)); columnSpacing: 12; rowSpacing: 12
                    Repeater {
                        model: backend.themePresets
                        ThemeChoice {
                            property bool controllerSelectable: true
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
                            property bool controllerSelectable: true
                            required property string modelData
                            width: 38; height: 38; enabled: !backend.busy; Accessible.name: "强调色 "+modelData
                            background: Rectangle { radius: 19; color: modelData; border.width: 3; border.color: backend.settings.accent_color===modelData ? Theme.text : "transparent" }
                            SelectionFrame { selected: parent.activeFocus; radius: 19 }
                            onClicked: backend.saveSettings({accent_color:modelData})
                        }
                    }
                    AppButton { property bool controllerSelectable: true; text: "跟随主题"; enabled: !backend.busy; onClicked: backend.saveSettings({accent_color:""}) }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    PadCheckBox { text: "界面动效"; checked: backend.settings.animations; enabled: !backend.busy; onToggled: backend.saveSettings({animations:checked}) }
                    PadCheckBox { text: "手柄导航"; checked: backend.settings.gamepad_enabled; enabled: !backend.busy; onToggled: backend.saveSettings({gamepad_enabled:checked}) }
                    PadCheckBox { text: "导航提示音"; checked: backend.settings.navigation_sounds; enabled: !backend.busy; onToggled: backend.saveSettings({navigation_sounds:checked}) }
                    RowLayout {
                        Layout.fillWidth: true;visible: backend.settings.navigation_sounds
                        AppComboBox { objectName: "navigationSoundStyle";model: ["首页 · 轻触","首页 · 轻柔","首页 · 清亮"];currentIndex: Math.max(0,["clear","soft","arcade"].indexOf(backend.settings.navigation_sound_style));onActivated: { backend.saveSettings({navigation_sound_style:["clear","soft","arcade"][currentIndex]});backend.previewNavigationSound(["clear","soft","arcade"][currentIndex],backend.settings.navigation_volume===undefined ? 80 : backend.settings.navigation_volume) } }
                        Slider { id: soundVolume;objectName: "navigationVolume";Layout.fillWidth: true;from: 0;to: 100;stepSize: 5;value: backend.settings.navigation_volume===undefined ? 80 : backend.settings.navigation_volume;onMoved: { if(!pressed) backend.saveSettings({navigation_volume:Math.round(value)});backend.previewNavigationVolume(Math.round(value)) } onPressedChanged: if(!pressed) backend.saveSettings({navigation_volume:Math.round(value)}) }
                        Label { text: Math.round(soundVolume.value)+"%";color: Theme.secondary }
                    }
                    Label { visible: backend.settings.navigation_sounds; text: "音效随布局切换：书柜翻书、影院放映机、星图轻响"; color: Theme.secondary; wrapMode: Text.Wrap; Layout.fillWidth: true }
                    Flow {
                        visible: backend.settings.navigation_sounds; Layout.fillWidth: true; Layout.preferredHeight: childrenRect.height; spacing: 6
                        Repeater {
                            model: [{id:"classic",name:"试听首页"},{id:"shelf",name:"试听书柜"},{id:"cinema",name:"试听影院"},{id:"atlas",name:"试听星图"}]
                            AppButton { required property var modelData; property bool controllerSelectable: true; objectName: "previewSound-"+modelData.id; text: modelData.name; flat: true; onClicked: backend.previewLayoutSound(modelData.id) }
                        }
                    }
                    PadCheckBox { text: "右摇杆控制卡片倾斜";checked: backend.settings.controller_tilt!==false;enabled: !backend.busy;onToggled: backend.saveSettings({controller_tilt:checked}) }
                    PadCheckBox { text: "自动备份通知"; checked: backend.settings.tray_notifications; enabled: !backend.busy; onToggled: backend.saveSettings({tray_notifications:checked}) }
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
