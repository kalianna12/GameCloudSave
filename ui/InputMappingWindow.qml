import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import QtQuick.Window
ApplicationWindow {
    id: window;objectName: "inputMappingWindow"
    width: 1360;height: 980;minimumWidth: 1040;minimumHeight: 700
    title: "手柄映射";color: Theme.background;font.family: "Microsoft YaHei UI"
    Material.theme: Theme.dark ? Material.Dark : Material.Light;Material.accent: Theme.accent
    readonly property var mapper: backend.mapping
    readonly property var profile: mapper.profile
    readonly property var live: mapper.live || ({})
    readonly property var axes: live.virtualAxes || [0,0,0,0]
    readonly property var padPreview: reverse ? ({buttons:(live.outputs || []).filter(function(t) { return t.indexOf("P:")===0 }).map(function(t) { return t.slice(2) }),LS:[axes[0],axes[1]],RS:[axes[2],axes[3]]}) : ({buttons:(live.buttons || []).concat(live.flashes || []),LS:live.LS || [0,0],RS:live.RS || [0,0]})
    readonly property bool reverse: profile.mode==="keys_to_pad"
    readonly property var stick: profile.forward.sticks[editingStick]
    property string editingStick: "LS"
    property bool appendCombo: false
    property bool navigateWithPad: false
    property var scrollView: null
    property var activeBindingChoice: null
    readonly property bool editingStickBinding: mapper.target.indexOf(editingStick+".")===0
    readonly property real mappingPanelHeight: Math.max(500,(window.width-100)*.46)+44
    readonly property var captureCancelItem: captureCancel
    property bool prepared: false
    readonly property bool editorReady: editorLoader.status===Loader.Ready
    Timer { interval: 600;running: !window.prepared && Qt.application.state===Qt.ApplicationActive && backend.watchInfo.running===0;onTriggered: window.prepared=true }
    signal returnRequested()
    onNavigateWithPadChanged: mapper.setAutoSelect(!navigateWithPad)
    onClosing: { mapper.setEditorVisible(false);returnRequested() }
    onVisibleChanged: { if(window.visible) mapper.bindWindow(window);mapper.setPreviewActive(window.active);mapper.setEditorVisible(window.visible && window.visibility!==Window.Minimized) }
    onVisibilityChanged: function(nextVisibility) { mapper.setEditorVisible(window.visible && nextVisibility!==Window.Minimized) }
    onActiveChanged: mapper.setPreviewActive(window.active)
    function openMapping() { mapper.bindWindow(window);show();raise();requestActivate() }
    function assign(source,target) { mapper.dropBinding(source,target,appendCombo) }
    function revealBindingEditor(item) {
        var view=window.scrollView
        if(view) { var items=view.contentItem,p=item.mapToItem(items,0,0);items.contentY=Math.max(0,Math.min(items.contentHeight-items.height,items.contentY+p.y-12)) }
    }
    function choices() {
        var list=[]
        function visit(item) { if(!item.visible || !item.enabled) return;if(item.controllerSelectable) list.push(item);for(var i=0;i<item.children.length;i++) visit(item.children[i]) }
        visit(templates.visible ? templates.contentItem : contentItem)
        if(templates.visible) visit(templates.footer)
        return list
    }
    function controllerInput(command) {
        if(mapper.state.recording) { if(command==="back") mapper.cancelCapture();return true }
        if(!navigateWithPad) return true
        if(activeBindingChoice && activeBindingChoice.controllerInput(command)) return true
        if(command==="back") { if(templates.visible) templates.close();else if(mapper.state.recording) mapper.cancelCapture();else close();return true }
        if(mapper.state.recording) return true
        var current=activeFocusItem,list=choices()
        while(current && list.indexOf(current)<0) current=current.parent
        if(!current) { if(list.length) list[0].forceActiveFocus();return true }
        if(command==="activate") { if(typeof current.activate==="function") current.activate();else { if(current.checkable) { current.toggle();current.toggled() };current.clicked() };return true }
        if(["left","right","up","down"].indexOf(command)<0) return true
        var point=current.mapToItem(contentItem,current.width/2,current.height/2),best=null,cost=Infinity
        list.forEach(function(candidate) {
            if(candidate===current) return
            var p=candidate.mapToItem(contentItem,candidate.width/2,candidate.height/2),dx=p.x-point.x,dy=p.y-point.y
            var along=command==="left" ? -dx : command==="right" ? dx : command==="up" ? -dy : dy
            var cross=command==="left" || command==="right" ? Math.abs(dy) : Math.abs(dx)
            if(along>1 && along+cross*2<cost) { cost=along+cross*2;best=candidate }
        })
        if(best) { best.forceActiveFocus();var scroll=templates.visible ? null : window.scrollView;if(scroll) { var p=best.mapToItem(scroll.contentItem,0,0);if(p.y<0) scroll.contentItem.contentY+=p.y;else if(p.y+best.height>scroll.height) scroll.contentItem.contentY+=p.y+best.height-scroll.height } }
        return true
    }
    component Action: AppButton { property bool controllerSelectable: true }
    component Caption: Label { color: Theme.secondary;Layout.fillWidth: true;wrapMode: Text.Wrap;font.pixelSize: 13 }
    Popup {
        id: capturePrompt;objectName: "mappingCapturePrompt"
        anchors.centerIn: parent;width: Math.min(500,window.width-80)
        visible: window.visible && window.mapper.state.recording
        modal: true;focus: true;closePolicy: Popup.NoAutoClose;padding: 24
        enter: Transition {}
        exit: Transition {}
        Overlay.modal: Rectangle { color: "#66000000" }
        contentItem: ColumnLayout {
            spacing: 16
            Label { text: "录入按键";color: Theme.text;font.pixelSize: 22;font.bold: true }
            Label { Layout.fillWidth: true;text: "按下组合键或滚动鼠标，全部松开后完成。";color: Theme.secondary;wrapMode: Text.Wrap }
            Label { Layout.fillWidth: true;text: (window.mapper.state.captured || []).join(" + ") || "等待输入";color: Theme.accent;font.pixelSize: 19;wrapMode: Text.Wrap }
            Action { id: captureCancel;objectName: "mappingCaptureCancel";text: "取消录入";Layout.alignment: Qt.AlignRight;onClicked: window.mapper.cancelCapture() }
        }
    }
    MappingTemplatesDialog { id: templates }
    component StickMeter: Item {
        property var values: [0,0]
        property string caption: ""
        implicitWidth: 90;implicitHeight: 112
        Rectangle {
            width: 80;height: 80;radius: 40;color: Theme.background;border.color: Theme.outline
            Rectangle { anchors.centerIn: parent;width: 1;height: parent.height-10;color: Theme.outline }
            Rectangle { anchors.centerIn: parent;width: parent.width-10;height: 1;color: Theme.outline }
            Rectangle { x: 33+parent.parent.values[0]*29;y: 33-parent.parent.values[1]*29;width: 14;height: 14;radius: 7;color: Theme.accent }
        }
        Label { anchors.bottom: parent.bottom;anchors.horizontalCenter: parent.horizontalCenter;text: parent.caption;color: Theme.secondary;font.pixelSize: 12 }
    }
    Dialog {
        id: drivers;objectName: "mappingDriverDialog";anchors.centerIn: parent;width: Math.min(650,window.width-64)
        title: "驱动与组件";modal: true;standardButtons: Dialog.Close
        Overlay.modal: Rectangle { color: "#66000000" }
        enter: Transition { NumberAnimation { property: "opacity";from: 0;to: 1;duration: Theme.motion ? 100 : 0 } }
        exit: Transition { NumberAnimation { property: "opacity";from: 1;to: 0;duration: Theme.motion ? 80 : 0 } }
        ColumnLayout {
            width: parent.width;spacing: 16
            Label { text: "手柄 → 键鼠";color: Theme.text;font.pixelSize: 18;font.bold: true }
            Caption { text: "无需额外驱动，支持系统识别的 XInput 手柄。" }
            Label { text: "键鼠 → 虚拟手柄";color: Theme.text;font.pixelSize: 18;font.bold: true }
            Caption { text: "映射模块："+(window.mapper.setup.state.package ? "已安装" : "未安装")+"\nViGEmBus 驱动："+(window.mapper.setup.state.driver ? "已安装" : "未安装") }
            Caption { text: window.mapper.setup.state.message }
            BusyIndicator { running: window.mapper.setup.state.busy;visible: running;Layout.preferredHeight: 32 }
            RowLayout {
                Action { objectName: "mappingDetect";text: "重新检测";enabled: !window.mapper.setup.state.busy;onClicked: window.mapper.setup.detect() }
                Action { objectName: "mappingInstall";text: "安装缺失组件";highlighted: true;enabled: !window.mapper.setup.state.busy && !window.mapper.setup.state.ready;onClicked: window.mapper.setup.install() }
            }
            Caption { text: "只安装缺失组件。驱动从官方 GitHub 下载，校验后打开 Windows 安装窗口，需要管理员授权；程序不会自动重启电脑。ViGEmBus 已停止维护。" }
            Action { text: "查看官方驱动发布页";onClicked: Qt.openUrlExternally("https://github.com/nefarius/ViGEmBus/releases/tag/v1.22.0") }
        }
    }
    Dialog {
        id: help;objectName: "mappingHelpDialog";anchors.centerIn: parent;width: 620;height: Math.min(560,window.height-64)
        title: "映射使用说明";modal: true;standardButtons: Dialog.Ok
        Overlay.modal: Rectangle { color: "#66000000" }
        enter: Transition { NumberAnimation { property: "opacity";from: 0;to: 1;duration: Theme.motion ? 100 : 0 } }
        exit: Transition { NumberAnimation { property: "opacity";from: 1;to: 0;duration: Theme.motion ? 80 : 0 } }
        contentItem: ScrollView {
            clip: true;contentWidth: availableWidth
            Label { width: parent.width;padding: 12;color: Theme.text;wrapMode: Text.Wrap;textFormat: Text.RichText
                text: "<b>点击编辑，拖动绑定</b><br>手柄→键鼠：点击手柄按键，再点击键盘，或把键帽拖到手柄上。键鼠→手柄：先选键鼠输入，再点手柄，或把手柄按键拖到键盘上。勾选追加可组合多个按键。<br><br><b>录入组合</b><br>点击录入后，按下组合并全部松开。支持左右 Ctrl / Shift / Alt、功能键及鼠标键，最多 12 键；不支持系统安全组合。<br><br><b>摇杆</b><br>详细设置位于页面最下方。轻推、重推分别设置八方向和附加键；可设置重推 Shift + WASD，也可反过来。鼠标速度、曲线、死区和平滑均可调。<br><br><b>开始与停止</b><br>启用时自动保存。切到游戏窗口，松开按键、回中摇杆后生效。本程序获得焦点时暂停输出；关闭此窗口后映射继续，退出程序停止。Ctrl + Alt + F12 随时停止；每次重启默认关闭。<br><br><b>模型与兼容</b><br>三种模型按物理位置对应标准 XInput 输入；PS / Joy-Con 需要先由系统或 Steam Input 转换为 XInput。切换图形不会安装对应实体手柄驱动，不支持未暴露为 XInput 的陀螺仪、触摸板、SL/SR 等专用输入。<br><br>保留原始键鼠与手柄输入，不隐藏设备；部分游戏的反作弊或权限限制可能拒绝模拟输入。"
            }
        }
    }
    Loader {
        id: editorLoader;anchors.fill: parent;active: window.visible || window.prepared;asynchronous: !window.visible
        sourceComponent: Component {
            ColumnLayout {
                anchors.fill: parent;anchors.margins: 24;spacing: 12
                RowLayout {
                    Layout.fillWidth: true;spacing: 12
                    Label { text: "手柄映射";color: Theme.text;font.pixelSize: 28;font.weight: Font.DemiBold }
                    AppComboBox { objectName: "mappingProfile";Layout.preferredWidth: 190;model: window.mapper.profiles;textRole: "name";wrapOptions: true;currentIndex: window.mapper.profiles.findIndex(function(p) { return p.id===window.mapper.profileId });onActivated: window.mapper.selectProfile(window.mapper.profiles[currentIndex].id);ToolTip.visible: hovered && !backend.controllerMode;ToolTip.text: currentText }
                    AppTextField { objectName: "mappingProfileName";Layout.preferredWidth: 180;text: window.profile.name;placeholderText: "配置名称";onEditingFinished: window.mapper.rename(text) }
                    Action { text: "配置管理";onClicked: profilesMenu.open();Menu { id: profilesMenu;MenuItem { text: "新建配置";onTriggered: window.mapper.createProfile() } MenuItem { text: "复制当前配置";onTriggered: window.mapper.duplicate() } MenuItem { text: "删除当前配置";enabled: window.mapper.profiles.length>1;onTriggered: window.mapper.deleteProfile() } } }
                    Item { Layout.fillWidth: true }
                    Label { text: window.mapper.state.dirty ? "未保存" : "";color: Theme.accent;font.pixelSize: 12 }
                    Action { objectName: "mappingSave";text: "保存配置";highlighted: true;onClicked: window.mapper.save() }
                    Action { objectName: "mappingClose";text: "关闭";onClicked: window.close() }
                }
                RowLayout {
                    Layout.fillWidth: true;spacing: 14
                    TabBar {
                        objectName: "mappingModes";Layout.preferredWidth: 340;Layout.minimumWidth: 300;currentIndex: window.reverse ? 1 : 0
                        TabButton { objectName: "mappingModeForward";text: "手柄到键鼠";font.pixelSize: 14;onClicked: window.mapper.setMode("pad_to_keys") }
                        TabButton { objectName: "mappingModeReverse";text: "键鼠到手柄";font.pixelSize: 14;onClicked: window.mapper.setMode("keys_to_pad") }
                    }
                    Switch { objectName: "mappingEnabled";text: "启用映射";checked: window.mapper.state.enabled;onToggled: window.mapper.setEnabled(checked) }
                    Item { Layout.fillWidth: true }
                    Action { objectName: "mappingTemplates";text: "游戏模板";onClicked: templates.open() }
                    Action { objectName: "mappingDrivers";text: "驱动与组件";onClicked: { window.mapper.setup.detect();drivers.open() } }
                    Action { objectName: "mappingHelp";text: "帮助";onClicked: help.open() }
                }
                RowLayout { Layout.fillWidth: true;Caption { objectName: "mappingStatus";text: window.mapper.dropHint || window.mapper.state.message;color: window.mapper.dropHint ? Theme.accent : Theme.secondary } Label { text: "Ctrl + Alt + F12 停止";color: Theme.secondary;font.pixelSize: 12 } }
                ScrollView {
                    id: scroll;objectName: "mappingScroll";Layout.fillWidth: true;Layout.fillHeight: true;clip: true;contentWidth: availableWidth;rightPadding: 14
                    ScrollBar.vertical.policy: ScrollBar.AlwaysOn;ScrollBar.horizontal.policy: ScrollBar.AlwaysOff
                    Component.onCompleted: window.scrollView=scroll
                    Component.onDestruction: window.scrollView=null
                    ColumnLayout {
                        width: scroll.availableWidth;spacing: 20
                        RowLayout { Layout.fillWidth: true;Label { text: "键盘与鼠标";color: Theme.text;font.pixelSize: 18;font.bold: true } Item { Layout.fillWidth: true } Caption { text: "点击选键 · 拖动绑定";Layout.fillWidth: false } }
                        MappingKeyboard {
                            objectName: "mappingKeyboardModel";Layout.fillWidth: true;Layout.preferredHeight: Math.min(implicitHeight,Math.max(205,scroll.height*.34))
                            selectedTokens: window.reverse ? window.mapper.sourceChord : window.mapper.currentChord
                            pressedTokens: window.mapper.keyboardPreview
                            onChosen: function(token) { window.mapper.chooseKey(token) }
                            onAssigned: function(source,target) { window.assign(source,target) }
                        }
                        MappingMouse {
                            Layout.fillWidth: true;Layout.preferredHeight: 48;selectedTokens: window.reverse ? window.mapper.sourceChord : window.mapper.currentChord
                            pressedTokens: window.mapper.keyboardPreview
                            onChosen: function(token) { window.mapper.chooseKey(token) }
                            onAssigned: function(source,target) { window.assign(source,target) }
                        }
                        RowLayout {
                            Layout.fillWidth: true;spacing: 20
                            Rectangle {
                                objectName: "mappingControllerPanel";Layout.fillWidth: true;Layout.preferredWidth: (window.width-100)*.57;Layout.preferredHeight: window.mappingPanelHeight
                                radius: 20;color: Theme.dark ? "#24282e" : "#ffffff";border.color: Theme.outline
                                ColumnLayout {
                                    anchors.fill: parent;anchors.margins: 18;spacing: 8
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Action { objectName: "mappingModel0";text: "Xbox";checkable: true;checked: window.mapper.padModel==="xbox";onClicked: window.mapper.setModel("xbox") }
                                        Action { objectName: "mappingModel1";text: "PS";checkable: true;checked: window.mapper.padModel==="ps";onClicked: window.mapper.setModel("ps") }
                                        Action { objectName: "mappingModel2";text: "Joy-Con";checkable: true;checked: window.mapper.padModel==="joycon";onClicked: window.mapper.setModel("joycon") }
                                        Item { Layout.fillWidth: true }
                                    }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Caption { text: window.reverse ? "虚拟手柄预览" : window.live.connected ? "已连接 P"+(window.live.slot+1) : "等待手柄连接" }
                                        AppComboBox { objectName: "mappingSlot";Layout.preferredWidth: 140;model: ["自动检测","P1","P2","P3","P4"];currentIndex: window.profile.slot+1;onActivated: window.mapper.setSlot(currentIndex-1) }
                                    }
                                    MappingGamepad {
                                        objectName: "mappingPadModel";Layout.fillWidth: true;Layout.fillHeight: true;Layout.minimumHeight: 200
                                        sample: window.padPreview;reverse: window.reverse;modelType: window.mapper.padModel
                                        selectedTokens: window.reverse ? window.mapper.currentChord : ["P:"+window.mapper.target]
                                        onChosen: function(token) { window.mapper.choosePad(token) }
                                        onAssigned: function(source,target) { window.assign(source,target) }
                                    }
                                }
                            }
                            Rectangle {
                                id: bindingPreviewPanel;objectName: "mappingPreviewPanel";Layout.fillWidth: true;Layout.preferredWidth: (window.width-100)*.43;Layout.preferredHeight: window.mappingPanelHeight
                                radius: 20;color: Theme.surface;border.color: Theme.outline
                                ColumnLayout {
                                    anchors.fill: parent;anchors.margins: 20;spacing: 10
                                    RowLayout { Layout.fillWidth: true;Label { text: "实时预览";color: Theme.text;font.pixelSize: 18;font.bold: true } Item { Layout.fillWidth: true } Label { text: window.mapper.state.enabled ? "已启用" : "仅预览";color: Theme.accent;font.pixelSize: 12 } }
                                    RowLayout {
                                        Layout.fillWidth: true;spacing: 16
                                        StickMeter { values: window.padPreview.LS || [0,0];caption: window.reverse ? "虚拟左摇杆" : "左摇杆" }
                                        StickMeter { values: window.padPreview.RS || [0,0];caption: window.reverse ? "虚拟右摇杆" : "右摇杆" }
                                        ColumnLayout { Layout.fillWidth: true;Caption { text: "映射输出" } Label { Layout.fillWidth: true;wrapMode: Text.Wrap;text: (window.live.outputs || []).map(function(t) { return window.mapper.label(t) }).concat((window.live.mouse || [0,0]).some(function(v) { return v!==0 }) ? ["鼠标移动"] : []).join(" + ") || "等待输入";color: Theme.accent;font.pixelSize: 17 } }
                                    }
                                    Rectangle { Layout.fillWidth: true;height: 1;color: Theme.outline }
                                    RowLayout {
                                        visible: window.reverse;Layout.fillWidth: true
                                        AppComboBox { objectName: "reverseRouteChoice";Layout.fillWidth: true;model: window.mapper.reverseRoutes;textRole: "label";wrapOptions: true;currentIndex: window.mapper.reverseRoutes.findIndex(function(row) { return row.id===window.mapper.target });onActivated: window.mapper.selectRoute(window.mapper.reverseRoutes[currentIndex].id) }
                                        Action { text: "删除绑定";onClicked: window.mapper.deleteRoute() }
                                    }
                                    RowLayout { Layout.fillWidth: true;Label { text: (window.reverse ? "输入：" : "编辑：")+window.mapper.bindingLabel;color: Theme.text;font.pixelSize: 15;font.bold: true;Layout.fillWidth: true;elide: Text.ElideRight } CheckBox { text: "追加组合";checked: window.appendCombo;onToggled: window.appendCombo=checked } }
                                    Label { objectName: "mappingChord";Layout.fillWidth: true;text: window.mapper.currentChord.map(function(t) { return window.mapper.label(t) }).join(" + ") || "未绑定";color: Theme.accent;wrapMode: Text.Wrap;font.pixelSize: 16 }
                                    RowLayout {
                                        Layout.fillWidth: true;spacing: 6
                                        Action { objectName: "mappingRecord";text: window.mapper.state.recording ? "停止录入" : "录入组合键";highlighted: window.mapper.state.recording;onClicked: { if(window.mapper.state.recording) window.mapper.cancelCapture();else window.mapper.record("binding") } }
                                        MappingKeyChoice { objectName: "mappingExtraKey";navigationHost: window;Layout.fillWidth: true;Layout.minimumWidth: 110 }
                                        Action { text: "清空";onClicked: window.mapper.setChord([]) }
                                    }
                                    Caption { visible: window.mapper.state.recording;text: "按下组合并全部松开："+(window.mapper.state.captured || []).join(" + ") }
                                    RowLayout {
                                        Layout.fillWidth: true
                                        Caption { text: "按下 "+window.mapper.history.totalPresses+" 次"+(!window.reverse && window.mapper.target.indexOf(".")<0 ? "　当前手柄按键 "+(window.mapper.history.pressCounts["P:"+window.mapper.target] || 0)+" 次" : "") }
                                        Action { text: "清除记录";flat: true;implicitHeight: 28;font.pixelSize: 12;onClicked: window.mapper.clearEvents() }
                                    }
                                    ListView {
                                        objectName: "mappingEventList";Layout.fillWidth: true;Layout.fillHeight: true;Layout.minimumHeight: 70;clip: true;model: window.mapper.history;spacing: 4
                                        delegate: RowLayout {
                                            required property string keyLabel;required property bool pressedDown;required property string timeLabel;width: ListView.view.width;height: 26;spacing: 12
                                            Label { text: timeLabel;color: Theme.secondary;font.pixelSize: 11;Layout.preferredWidth: 90 }
                                            Label { text: keyLabel;color: Theme.text;font.pixelSize: 12;Layout.preferredWidth: 90;elide: Text.ElideRight }
                                            Label { text: pressedDown ? "按下" : "松开";color: pressedDown ? Theme.accent : Theme.secondary;font.pixelSize: 12 }
                                            Item { Layout.fillWidth: true }
                                        }
                                    }
                                }
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Label { text: "详细设置";color: Theme.text;font.pixelSize: 21;font.bold: true }
                            Item { Layout.fillWidth: true }
                            CheckBox { text: "手柄导航界面";checked: window.navigateWithPad;onToggled: window.navigateWithPad=checked }
                            Action { text: "恢复默认配置";onClicked: window.mapper.reset() }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true;visible: !window.reverse;spacing: 16
                            RowLayout {
                                Layout.fillWidth: true
                                Label { text: "摇杆";color: Theme.text;font.pixelSize: 17;font.weight: Font.DemiBold }
                                AppComboBox { objectName: "mappingStickChoice";Layout.preferredWidth: 145;model: ["左摇杆","右摇杆"];currentIndex: window.editingStick==="LS" ? 0 : 1;onActivated: { window.editingStick=currentIndex===0 ? "LS" : "RS";window.mapper.selectTarget(window.editingStick+".light.N") } }
                                AppComboBox { objectName: "mappingStickMode";Layout.preferredWidth: 160;model: ["八向按键","鼠标移动","鼠标滚轮","停用"];currentIndex: ["keys","mouse","wheel","disabled"].indexOf(window.stick.mode);onActivated: window.mapper.setOption(window.editingStick,"mode",["keys","mouse","wheel","disabled"][currentIndex]) }
                                Item { Layout.fillWidth: true }
                                Action { objectName: "mappingBothWasd";visible: window.stick.mode==="keys";text: "两组用 WASD";onClicked: window.mapper.applyStickPreset(window.editingStick,"both","wasd") }
                                Action { objectName: "mappingBothArrows";visible: window.stick.mode==="keys";text: "两组用方向键";onClicked: window.mapper.applyStickPreset(window.editingStick,"both","arrows") }
                            }
                            RowLayout {
                                Layout.fillWidth: true;spacing: 28;visible: window.stick.mode!=="disabled"
                                Caption { text: "死区 "+Math.round(window.stick.deadzone*100)+"%";Layout.fillWidth: false;Layout.preferredWidth: 90 }
                                Slider { objectName: "mappingDeadzone";Layout.fillWidth: true;from: .05;to: Math.min(.6,window.stick.threshold-.08);value: window.stick.deadzone;onMoved: window.mapper.setOption(window.editingStick,"deadzone",Math.round(value*100)/100) }
                                Caption { visible: window.stick.mode!=="mouse";text: "重推阈值 "+Math.round(window.stick.threshold*100)+"%";Layout.fillWidth: false;Layout.preferredWidth: 120 }
                                Slider { objectName: "mappingThreshold";visible: window.stick.mode!=="mouse";Layout.fillWidth: true;from: window.stick.deadzone+.08;to: .99;value: window.stick.threshold;onMoved: window.mapper.setOption(window.editingStick,"threshold",Math.round(value*100)/100) }
                            }
                            RowLayout {
                                visible: window.stick.mode==="keys";Layout.fillWidth: true;spacing: 20
                                MappingStickBindings { Layout.fillWidth: true;Layout.preferredWidth: 1;stickId: window.editingStick;zone: "light";config: window.stick;onAssigned: function(source,target) { window.assign(source,target) } }
                                MappingStickBindings { Layout.fillWidth: true;Layout.preferredWidth: 1;stickId: window.editingStick;zone: "hard";config: window.stick;onAssigned: function(source,target) { window.assign(source,target) } }
                            }
                            RowLayout {
                                visible: window.stick.mode==="keys";Layout.fillWidth: true
                                Label { text: window.editingStickBinding ? window.mapper.bindingLabel : "选择方向或附加键";color: Theme.text;font.pixelSize: 14 }
                                Caption { text: window.editingStickBinding ? window.mapper.currentChord.map(function(t) { return window.mapper.label(t) }).join(" + ") || "未绑定" : "";color: Theme.accent }
                                Action { objectName: "mappingStickRecord";enabled: window.editingStickBinding;text: window.mapper.state.recording ? "停止录入" : "录入组合键";highlighted: window.mapper.state.recording;onClicked: { if(window.mapper.state.recording) window.mapper.cancelCapture();else window.mapper.record("binding") } }
                                MappingKeyChoice { objectName: "mappingStickExtraKey";navigationHost: window;enabled: window.editingStickBinding }
                                Action { objectName: "mappingStickClear";enabled: window.editingStickBinding;text: "清空";onClicked: window.mapper.setChord([]) }
                            }
                            RowLayout {
                                visible: window.stick.mode==="wheel";Layout.fillWidth: true;spacing: 20
                                Caption { text: "轻推（格 / 秒）";Layout.fillWidth: false }
                                CompactSpinBox { objectName: "mappingWheelLight";from: 1;to: 30;value: window.stick.wheelLight;onValueModified: window.mapper.setOption(window.editingStick,"wheelLight",value) }
                                Caption { text: "重推（格 / 秒）";Layout.fillWidth: false }
                                CompactSpinBox { objectName: "mappingWheelHard";from: 1;to: 30;value: window.stick.wheelHard;onValueModified: window.mapper.setOption(window.editingStick,"wheelHard",value) }
                                CheckBox { text: "反向滚动";checked: window.stick.wheelInvert;onToggled: window.mapper.setOption(window.editingStick,"wheelInvert",checked) }
                                Item { Layout.fillWidth: true }
                            }
                            RowLayout { visible: window.stick.mode==="mouse";Layout.fillWidth: true;Caption { text: "鼠标速度（像素 / 秒）" } CompactSpinBox { objectName: "mappingMouseSpeed";from: 100;to: 5000;stepSize: 50;value: window.stick.speed;onValueModified: window.mapper.setOption(window.editingStick,"speed",value) } }
                            RowLayout { visible: window.stick.mode==="mouse";Layout.fillWidth: true;Caption { text: "响应曲线 "+window.stick.curve.toFixed(1) } Slider { Layout.preferredWidth: 230;from: .5;to: 3.5;value: window.stick.curve;onMoved: window.mapper.setOption(window.editingStick,"curve",Math.round(value*10)/10) } }
                            RowLayout { visible: window.stick.mode==="mouse";Layout.fillWidth: true;Caption { text: "平滑（毫秒）" } CompactSpinBox { from: 0;to: 150;stepSize: 5;value: window.stick.smoothing;onValueModified: window.mapper.setOption(window.editingStick,"smoothing",value) } }
                        }
                        RowLayout {
                            Layout.fillWidth: true;visible: window.reverse;spacing: 32
                            ColumnLayout {
                                Layout.fillWidth: true;Layout.preferredWidth: 1;Layout.alignment: Qt.AlignTop;spacing: 12
                                Label { text: "摇杆力度";color: Theme.text;font.pixelSize: 17;font.weight: Font.DemiBold }
                                RowLayout { Layout.fillWidth: true;Caption { text: "重推 "+Math.round(window.profile.reverse.strength*100)+"%";Layout.preferredWidth: 95;Layout.fillWidth: false } Slider { Layout.fillWidth: true;from: .1;to: 1;value: window.profile.reverse.strength;onMoved: window.mapper.setOption("reverse","strength",Math.round(value*100)/100) } }
                                RowLayout { Layout.fillWidth: true;Caption { text: "轻推 "+Math.round(window.profile.reverse.lightStrength*100)+"%";Layout.preferredWidth: 95;Layout.fillWidth: false } Slider { Layout.fillWidth: true;from: .1;to: 1;value: window.profile.reverse.lightStrength;onMoved: window.mapper.setOption("reverse","lightStrength",Math.round(value*100)/100) } }
                                RowLayout { Layout.fillWidth: true;Caption { text: "轻推键："+(window.profile.reverse.lightModifier.map(function(t) { return window.mapper.label(t) }).join(" + ") || "无") } Action { text: "录入";onClicked: window.mapper.record("lightModifier") } Action { text: "清除";onClicked: window.mapper.setOption("reverse","lightModifier",[]) } }
                                RowLayout { Layout.fillWidth: true;Caption { text: "过渡（毫秒）" } CompactSpinBox { from: 0;to: 500;stepSize: 10;value: window.profile.reverse.ramp;onValueModified: window.mapper.setOption("reverse","ramp",value) } }
                                Label { text: "鼠标移动";color: Theme.text;font.pixelSize: 17;font.weight: Font.DemiBold;Layout.topMargin: 8 }
                                RowLayout { Layout.fillWidth: true;Caption { text: "目标摇杆" } AppComboBox { Layout.preferredWidth: 150;model: ["右摇杆","左摇杆","停用"];currentIndex: ["RS","LS","disabled"].indexOf(window.profile.reverse.mouse);onActivated: window.mapper.setOption("reverse","mouse",["RS","LS","disabled"][currentIndex]) } }
                                RowLayout { Layout.fillWidth: true;Caption { text: "满推速度（像素 / 秒）" } CompactSpinBox { from: 100;to: 5000;stepSize: 50;value: window.profile.reverse.mouseSpeed;onValueModified: window.mapper.setOption("reverse","mouseSpeed",value) } }
                                RowLayout { Layout.fillWidth: true;Caption { text: "平滑（毫秒）" } CompactSpinBox { from: 0;to: 150;stepSize: 5;value: window.profile.reverse.smoothing;onValueModified: window.mapper.setOption("reverse","smoothing",value) } }
                            }
                            MappingWheelBindings { Layout.fillWidth: true;Layout.preferredWidth: 1;Layout.alignment: Qt.AlignTop;config: window.profile.reverse;onEditRequested: window.revealBindingEditor(bindingPreviewPanel) }
                        }
                        Item { Layout.preferredHeight: 14 }
                    }
                }
            }
        }
    }
    BusyIndicator { anchors.centerIn: parent;running: window.visible && editorLoader.status===Loader.Loading;visible: running }
}
