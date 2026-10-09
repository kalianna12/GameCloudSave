import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: setup; width: 1020; height: 760; minimumWidth: 900; minimumHeight: 650
    title: "首次使用设置"; color: Theme.background; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent; font.family: "Microsoft YaHei UI"; modality: Qt.ApplicationModal
    property int step: 0
    property var skipped: ({})
    property bool finishing: false
    property var titles: ["开始使用","Playnite（可选）","本地备份","AList / WebDAV（可选）","DeepSeek（可选）","封面来源","显示与后台","检查设置"]
    signal finished()
    function advance(skip) { if(step>=7) return;var next=Object.assign({},skipped);if(skip) next[step]=true;else delete next[step];skipped=next;step++;scroll.contentItem.contentY=0 }
    function values() {
        var v={setup_completed:true,guide_dismissed:true}
        if(!skipped[1]) { v.playnite=usePlaynite.checked ? playnite.text : "";v.library=usePlaynite.checked ? library.text : "" }
        if(!skipped[2]) v.snapshots=snapshots.text
        if(!skipped[3]) { v.dav_url=server.text;v.dav_user=user.text;v.password=password.text;v.cloud_folder=cloudFolder.text }
        if(!skipped[4]) { v.ai_enabled=aiEnabled.checked;v.ai_model=model.text;v.ai_key=apiKey.text }
        if(!skipped[5]) { v.cover_source=provider.currentValue;v.custom_cover_url=customUrl.text }
        if(!skipped[6]) { v.watch=watch.checked;v.watch_upload=upload.checked;v.close_to_tray=tray.checked;v.watch_interval=interval.value;v.cover_size=size.value;v.columns=columns.value;v.gap=gap.value }
        return v
    }
    function openWizard() {
        var s=backend.settings;step=0;skipped=({});finishing=false
        usePlaynite.checked=!!s.playnite;playnite.text=s.playnite;library.text=s.library;snapshots.text=s.snapshots
        server.text=s.dav_url;user.text=s.dav_user;password.text="";cloudFolder.text=s.cloud_folder
        aiEnabled.checked=s.ai_enabled;model.text=s.ai_model;apiKey.text=""
        provider.currentIndex=Math.max(0,backend.coverProviders.findIndex(function(row) { return row.id===s.cover_source }));customUrl.text=s.custom_cover_url
        watch.checked=s.watch;upload.checked=s.watch_upload;tray.checked=s.close_to_tray;interval.value=s.watch_interval;size.value=s.cover_size;columns.value=s.columns;gap.value=s.gap
        show();raise();requestActivate()
    }
    onVisibleChanged: if(!visible) { password.text="";apiKey.text="" }
    Connections { target: backend; function onSettingsChanged() {
        if(cloud.visible) { server.text=backend.settings.dav_url;user.text=backend.settings.dav_user;cloudFolder.text=backend.settings.cloud_folder;password.text="" }
        if(setup.finishing && backend.settings.setup_completed) { setup.finishing=false;setup.close();setup.finished() }
    } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 18
        RowLayout { Label { text: "设置 GameCloudSave"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } Label { text: backend.settings.computer; color: Theme.secondary } }
        RowLayout { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 24
            ColumnLayout { Layout.preferredWidth: 190; Layout.alignment: Qt.AlignTop; spacing: 14
                Repeater { model: setup.titles; Label { required property string modelData; required property int index; text:(index+1)+". "+modelData; font.bold: setup.step===index; color: setup.step===index ? Theme.accent : Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap } }
            }
            ScrollView { id: scroll; Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                ColumnLayout { width: scroll.availableWidth-14; spacing: 14
                    Label { text: setup.titles[setup.step]; font.pixelSize: 23; font.bold: true }
                    ColumnLayout { visible: setup.step===0; Layout.fillWidth: true; spacing: 18
                        Label { text: "先完成常用设置，再导入游戏。"; font.pixelSize: 18 }
                        Label { text: "没有 Playnite 也能使用。云端和 AI 都可跳过，先在本地备份。每台电脑分别设置自己的游戏和存档路径。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                        Label { text: "本项目开源，采用 MIT 许可。游戏、封面和第三方组件遵循各自许可。恢复前会备份当前存档，匹配结果仍需核对。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                        AppButton { text: "查看开源说明"; onClicked: notices.open() }
                    }
                    ColumnLayout { visible: setup.step===1; Layout.fillWidth: true; spacing: 12
                        CheckBox { id: usePlaynite; text: "使用 Playnite 游戏库" }
                        Label { text: "不用 Playnite 可跳过，之后从游戏平台或本地文件夹导入。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                        Label { text: "Playnite 程序目录" }
                        RowLayout { AppTextField { id: playnite; enabled: usePlaynite.checked; Layout.fillWidth: true } AppButton { text: "选择"; enabled: usePlaynite.checked; onClicked: { var p=backend.pickFolder(playnite.text);if(p) playnite.text=p } } }
                        Label { text: "library 目录（包含 games.db）" }
                        RowLayout { AppTextField { id: library; enabled: usePlaynite.checked; Layout.fillWidth: true } AppButton { text: "选择"; enabled: usePlaynite.checked; onClicked: { var p=backend.pickFolder(library.text);if(p) library.text=p } } }
                    }
                    ColumnLayout { visible: setup.step===2; Layout.fillWidth: true; spacing: 12
                        Label { text: "本机备份目录" }
                        RowLayout { AppTextField { id: snapshots; Layout.fillWidth: true } AppButton { text: "选择"; onClicked: { var p=backend.pickFolder(snapshots.text);if(p) snapshots.text=p } } }
                        Label { text: "存档先备份到这里，再尝试上传。可选择空间充足的磁盘；游戏存档目录在导入后分别设置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    }
                    ColumnLayout { visible: setup.step===3; Layout.fillWidth: true; spacing: 10
                        Label { text: "WebDAV 地址" } AppTextField { id: server; Layout.fillWidth: true; placeholderText: "https://服务器/dav/" }
                        Label { text: "用户名" } AppTextField { id: user; Layout.fillWidth: true }
                        Label { text: "密码（留空保持已保存密码）" } AppTextField { id: password; Layout.fillWidth: true; echoMode: TextInput.Password }
                        Label { text: "云端备份文件夹" } AppTextField { id: cloudFolder; Layout.fillWidth: true; placeholderText: "例如：百度网盘/game-saves" }
                        AppButton { text: "连接、浏览并选择文件夹"; enabled: !backend.busy; onClicked: cloud.openBrowserDraft({dav_url:server.text,dav_user:user.text,password:password.text,cloud_folder:cloudFolder.text}) }
                        AppButton { text: "采用已保存的云端位置"; onClicked: cloudFolder.text=backend.settings.cloud_folder }
                        Label { text: "可跳过，稍后在云端存储中验证并选择文件夹。统一位置按游戏名和存档目录分组。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    }
                    ColumnLayout { visible: setup.step===4; Layout.fillWidth: true; spacing: 12
                        Switch { id: aiEnabled; text: "启用 DeepSeek" }
                        Label { text: "模型" } AppTextField { id: model; Layout.fillWidth: true }
                        Label { text: "API Key" } AppTextField { id: apiKey; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_ai_key ? "已保存，留空保持" : "可跳过，仍可使用本地规则" }
                        AppButton { text: "保存并测试 AI 连接"; enabled: !backend.busy; onClicked: backend.testAi({ai_enabled:aiEnabled.checked,ai_model:model.text,ai_key:apiKey.text}) }
                        Label { text: backend.aiConnection; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    }
                    ColumnLayout { visible: setup.step===5; Layout.fillWidth: true; spacing: 12
                        ComboBox { id: provider; Layout.fillWidth: true; model: backend.coverProviders; textRole: "label"; valueRole: "id" }
                        Label { text: "Playnite 已有封面直接读取。本地游戏可搜索封面，或用 AI 辅助匹配名称。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                        Label { visible: provider.currentValue==="custom"; text: "自定义 JSON 搜索地址（含 {query}）" }
                        AppTextField { id: customUrl; visible: provider.currentValue==="custom"; Layout.fillWidth: true; placeholderText: "https://服务/search?q={query}" }
                    }
                    ColumnLayout { visible: setup.step===6; Layout.fillWidth: true; spacing: 10
                        CheckBox { id: tray; text: "关闭主窗口后留在托盘" }
                        CheckBox { id: watch; text: "监听游戏启动与退出并自动备份" }
                        CheckBox { id: upload; text: "自动备份后上传云端"; enabled: watch.checked }
                        RowLayout { Label { text: "监听间隔（秒）"; Layout.fillWidth: true } CompactSpinBox { id: interval; from: 5; to: 60; stepSize: 5 } }
                        RowLayout { Label { text: "封面大小"; Layout.fillWidth: true } CompactSpinBox { id: size; from: 196; to: 360; stepSize: 4 } }
                        RowLayout { Label { text: "每行数量（0 为自动）"; Layout.fillWidth: true } CompactSpinBox { id: columns; from: 0; to: 10 } }
                        RowLayout { Label { text: "卡片间隔"; Layout.fillWidth: true } CompactSpinBox { id: gap; from: 8; to: 48; stepSize: 2 } }
                    }
                    ColumnLayout { visible: setup.step===7; Layout.fillWidth: true; spacing: 12
                        Repeater { model: [{title:"Playnite",page:1,value:usePlaynite.checked ? playnite.text+"\n"+library.text : "不使用"},{title:"本地备份",page:2,value:snapshots.text},{title:"云端",page:3,value:server.text+"\n"+(cloudFolder.text || "未选择文件夹")},{title:"DeepSeek",page:4,value:aiEnabled.checked ? model.text+" / "+(apiKey.text || backend.settings.has_ai_key ? "Key 已设置" : "未填写 Key") : "关闭"},{title:"封面来源",page:5,value:provider.currentText},{title:"后台与显示",page:6,value:(tray.checked ? "托盘运行" : "关闭时退出")+" / "+(watch.checked ? "监听开启" : "监听关闭")+"\n封面 "+size.value+"，每行 "+columns.value+"，间隔 "+gap.value}]
                            ColumnLayout { required property var modelData; Layout.fillWidth: true
                                Label { text: modelData.title; font.bold: true }
                                Label { text: setup.skipped[modelData.page] ? "已跳过，保留当前设置" : modelData.value; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                            }
                        }
                    }
                }
            }
        }
        Label { text: backend.status; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            AppButton { text: "上一步"; enabled: !backend.busy && setup.step>0; onClicked: { setup.step--;scroll.contentItem.contentY=0 } }
            AppButton { text: "跳过此页"; visible: setup.step>0 && setup.step<7; enabled: !backend.busy; onClicked: setup.advance(true) }
            Item { Layout.fillWidth: true }
            AppButton { text: setup.step===7 ? "保存并完成" : "下一步"; enabled: !backend.busy; highlighted: true; onClicked: { if(setup.step===7) { setup.finishing=true;backend.saveSetup(setup.values()) }else setup.advance(false) } }
        }
    }
    CloudWindow { id: cloud; modality: Qt.ApplicationModal }
    Dialog { id: notices; title: "开源说明"; anchors.centerIn: parent; width: 650; height: 400; modal: true; standardButtons: Dialog.Close
        contentItem: ScrollView { TextArea { text: backend.openSourceNotice; readOnly: true; wrapMode: Text.Wrap } }
    }
}
