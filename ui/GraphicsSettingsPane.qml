import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "ControllerForm.js" as Form

ScrollView {
    id: pane
    objectName: "graphicsSettingsPane"
    property string gameId: ""
    property bool dirty: false
    property bool saving: false
    readonly property var core: backend.graphics.state
    clip: true
    contentWidth: availableWidth
    function loadFor(ident) {
        gameId=ident
        loadValues(backend.graphics.profile(ident));dirty=false;saving=false
    }
    function loadValues(p) {
        enabledToggle.checked=p.enabled;automatic.checked=p.auto_start
        algorithm.currentIndex=Math.max(0,backend.graphics.presets.map(function(v) { return v.id }).indexOf(p.preset))
        sharpness.value=p.sharpness;display.currentIndex=p.display==="windowed" ? 1 : 0
        fit.currentIndex=p.fit==="stretch" ? 1 : 0;windowScale.value=Math.round(p.window_scale*100)
        capture.currentIndex=p.capture===3 ? 1 : 0;fps.value=p.fps;mode3d.checked=p.game_3d
    }
    function controllerInput(command) { return Form.handle([quickChoice,applyQuick,enabledToggle,algorithm,sharpness,display,fit,windowScale,fps,automatic,mode3d,capture,installButton,importButton,downloadButton,applyButton,stopButton,logsButton],Window.window.activeFocusItem,command,pane) }
    function values() {
        return {enabled:enabledToggle.checked,auto_start:automatic.checked,
            preset:backend.graphics.presets[algorithm.currentIndex].id,sharpness:Math.round(sharpness.value),
            display:display.currentIndex===1 ? "windowed" : "fullscreen",fit:fit.currentIndex===1 ? "stretch" : "fit",
            window_scale:windowScale.value/100,capture:capture.currentIndex===1 ? 3 : 0,fps:fps.value,game_3d:mode3d.checked}
    }
    function save() { saving=true;backend.graphics.save(gameId,values()) }
    Connections {
        target: backend.graphics
        function onSaved(ident) { if(ident===pane.gameId) { pane.dirty=false;pane.saving=false } }
        function onChanged() { if(!pane.core.busy && pane.core.phase==="error") pane.saving=false }
    }
    ColumnLayout {
        width: pane.availableWidth
        spacing: 16
        RowLayout {
            Layout.fillWidth: true
            AppComboBox { id: quickChoice;objectName: "graphicsQuickProfile";Layout.fillWidth: true;model: backend.graphics.quickProfiles;textRole: "name" }
            AppButton { id: applyQuick;objectName: "graphicsUseQuick";text: "使用预设";enabled: !pane.core.busy;onClicked: { pane.loadValues(backend.graphics.quickProfile(quickChoice.currentIndex));pane.dirty=true } }
        }
        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true; spacing: 4
                Label { text: "为这款游戏增强画质"; font.pixelSize: 19; font.bold: true }
                Label { text: "方案单独保存，不改变游戏文件。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
            }
            Switch { id: enabledToggle; objectName: "graphicsEnabled"; enabled: pane.core.supported && !pane.core.busy; onToggled: pane.dirty=true; Accessible.name: "启用本游戏画质增强" }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: help.implicitHeight+24
            radius: Theme.radius; color: Theme.selection; border.color: Theme.outline
            Label {
                id: help; anchors.fill: parent; anchors.margins: 12
                text: "先将游戏设为窗口模式，保留原始分辨率，再由画质增强放大。Ctrl+Alt+F11 随时切换；鼠标点击位置由内核同步。"
                wrapMode: Text.Wrap; color: Theme.text
            }
        }
        Label {
            objectName: "graphicsOutputResolution";Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.accent
            readonly property int pixelsWide: Math.round(Screen.width*Screen.devicePixelRatio)
            readonly property int pixelsHigh: Math.round(Screen.height*Screen.devicePixelRatio)
            text: display.currentIndex===0 ? "全屏目标：游戏所在显示器的物理分辨率（当前屏幕 "+pixelsWide+" × "+pixelsHigh+"）。"+(fit.currentIndex===0 ? " 保持比例时可能留黑边。" : " 拉伸铺满整个屏幕。") : "窗口目标：原始游戏画面宽、高各 × "+(windowScale.value/100).toFixed(2)+"，例如 1280 × 720 → "+Math.round(1280*windowScale.value/100)+" × "+Math.round(720*windowScale.value/100)+"；以屏幕可容纳范围为限。"
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Magpie "+pane.core.version+" · "+(pane.core.installed ? "内核已安装" : "首次使用需安装内核"); color: pane.core.installed ? Theme.accent : Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
        Flow {
            visible: !pane.core.installed; Layout.fillWidth: true; spacing: 8
            AppButton { id: installButton;objectName: "graphicsInstall"; text: "下载并安装内核"; highlighted: true; enabled: !pane.core.busy && pane.core.supported; onClicked: backend.graphics.install() }
            AppButton { id: importButton;text: "导入官方 ZIP"; enabled: !pane.core.busy && pane.core.supported; onClicked: backend.graphics.importArchive() }
            AppButton { id: downloadButton;text: "官方下载页"; onClicked: backend.graphics.openDownload() }
        }
        Label { visible: !pane.core.supported; text: "需要 Windows 10 1903 或更新系统，以及支持 DirectX 11 的显卡。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            visible: pane.core.busy && !pane.core.installed; Layout.fillWidth: true
            AppBusyIndicator { running: parent.visible; implicitWidth: 20; implicitHeight: 20 }
            Label { text: pane.core.message; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
            AppButton { text: "取消"; onClicked: backend.graphics.cancel() }
        }
        Label { visible: !pane.core.installed && pane.core.phase==="error"; text: pane.core.message; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 10; enabled: enabledToggle.checked && !pane.core.busy
            Label { text: "算法与锐化"; font.bold: true }
            AppComboBox { id: algorithm; objectName: "graphicsAlgorithm"; Layout.fillWidth: true; model: backend.graphics.presets; textRole: "name"; onActivated: pane.dirty=true }
            Label { text: backend.graphics.presets[algorithm.currentIndex].description; color: Theme.secondary; wrapMode: Text.Wrap; Layout.fillWidth: true }
            RowLayout {
                Layout.fillWidth: true; visible: algorithm.currentIndex!==4
                Label { text: "锐化（非分辨率）"; Layout.preferredWidth: 130 }
                Slider { id: sharpness; objectName: "graphicsSharpness"; Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; onMoved: pane.dirty=true; Accessible.name: "锐化强度" }
                Label { text: Math.round(sharpness.value)+"%"; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight }
            }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.outline }
            Label { text: "画面输出"; font.bold: true; Layout.topMargin: 4 }
            GridLayout {
                columns: 2; Layout.fillWidth: true; rowSpacing: 10; columnSpacing: 18
                Label { text: "显示方式" }
                AppComboBox { id: display; objectName: "graphicsDisplay"; Layout.fillWidth: true; model: ["全屏放大","窗口放大"]; onActivated: { if(currentIndex===1) mode3d.checked=false;pane.dirty=true } }
                Label { text: display.currentIndex===0 ? "画面比例" : "窗口倍数" }
                AppComboBox { id: fit; Layout.fillWidth: true; visible: display.currentIndex===0; model: ["保持比例（推荐）","拉伸铺满"]; onActivated: pane.dirty=true }
                SpinBox { id: windowScale; Layout.fillWidth: true; visible: display.currentIndex===1; from: 125; to: 400; stepSize: 25; value: 200; textFromValue: function(v) { return (v/100).toFixed(2)+"×" }; onValueModified: pane.dirty=true; Accessible.name: "窗口放大倍数" }
                Label { text: "输出帧率上限" }
                SpinBox { id: fps; Layout.fillWidth: true; from: 30; to: 240; stepSize: 10; value: 60; editable: true; onValueModified: pane.dirty=true; Accessible.name: "输出帧率上限" }
            }
            Label { text: "帧率上限用于控制 GPU 开销，不会增加游戏帧数。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.outline }
            Label { text: "启动与兼容性"; font.bold: true; Layout.topMargin: 4 }
            CheckBox { id: automatic; objectName: "graphicsAutomatic"; text: "从游戏库启动游戏时自动启用"; onToggled: pane.dirty=true }
            CheckBox { id: mode3d; text: "3D 游戏鼠标模式"; enabled: display.currentIndex===0; onToggled: pane.dirty=true }
            Label { text: "FPS / TPS 视角控制可启用 3D 模式；Galgame、菜单和鼠标光标操作请保持关闭。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 12 }
            RowLayout {
                Layout.fillWidth: true
                Label { text: "窗口捕获"; Layout.preferredWidth: 90 }
                AppComboBox { id: capture; Layout.fillWidth: true; model: ["Windows Graphics Capture（推荐）","DWM 兼容模式"]; onActivated: pane.dirty=true }
            }
        }
        Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: Theme.outline }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "运行状态"; font.bold: true; Layout.fillWidth: true }
        }
        Flow {
            Layout.fillWidth: true; spacing: 8
            AppButton { id: applyButton;objectName: "graphicsApply"; text: "应用到已运行游戏"; visible: pane.core.installed; enabled: enabledToggle.checked && !pane.dirty && !pane.core.busy; onClicked: backend.graphics.apply(pane.gameId) }
            AppButton { id: stopButton;text: "停止增强"; visible: pane.core.installed; enabled: !pane.core.busy && ["active","ready"].indexOf(pane.core.phase)>=0; onClicked: backend.graphics.stop() }
            AppButton { id: logsButton;text: "查看内核日志"; visible: pane.core.installed; onClicked: backend.graphics.openLogs() }
            AppButton { text: "取消"; visible: pane.core.busy && ["installing","starting"].indexOf(pane.core.phase)>=0; onClicked: backend.graphics.cancel() }
        }
        RowLayout {
            Layout.fillWidth: true
            AppBusyIndicator { running: pane.core.busy; visible: running; implicitWidth: 20; implicitHeight: 20 }
            Label { objectName: "graphicsMessage"; text: pane.core.phase==="error" ? pane.core.message : pane.dirty ? "方案有修改，请先保存。" : pane.core.message; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
        Label { text: "内核独立运行，仅增强捕获到的画面；首次使用着色器时可能稍等片刻。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
        Item { implicitHeight: 4 }
    }
}
