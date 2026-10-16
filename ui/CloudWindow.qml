import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: cloud
    width: 1180; height: 820; minimumWidth: 920; minimumHeight: 680
    title: "云端存储"
    color: Theme.background; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    font.family: "Microsoft YaHei UI"
    property string selectedName: ""
    property var selectedEntry: ({})
    Connections { target: backend; function onDirectoriesChanged() { if(cloud.visible && configTabs.currentIndex===1) configTabs.currentIndex=0 } }
    property var visibleEntries: backend.directories.filter(function(entry) {
        return (!foldersOnly.checked || entry.IsDir) && (showHidden.checked || entry.Name[0]!==".") && entry.Name.toLowerCase().indexOf(fileSearch.text.trim().toLowerCase())>=0
    }).sort(function(a,b) {
        if(a.IsDir!==b.IsDir) return a.IsDir ? -1 : 1
        if(fileSort.currentIndex===1) return (b.ModTime || "").localeCompare(a.ModTime || "") || a.Name.localeCompare(b.Name)
        if(fileSort.currentIndex===2) return b.Size-a.Size || a.Name.localeCompare(b.Name)
        return a.Name.localeCompare(b.Name)
    })
    function fileSize(bytes) { return bytes<1024 ? bytes+" B" : bytes<1048576 ? (bytes/1024).toFixed(1)+" KB" : (bytes/1048576).toFixed(1)+" MB" }
    function entryLabel(entry) {
        var game=backend.games.find(function(game) { return game.id===entry.Name })
        return entry.IsDir && game ? game.name+"（旧备份）" : entry.Name
    }
    function values() { return {dav_url:server.text,dav_user:user.text,password:password.text,rclone:rclonePath.text,cloud_folder:storage.text,cloud_separate_computer:separateComputer.checked,cloud_retries:retryCount.value,cloud_timeout:timeoutSeconds.value,watch_upload:watchUpload.checked} }
    function openBrowser() {
        openBrowserDraft({})
    }
    function openConnectionSettings() { configTabs.currentIndex=1;openBrowserDraft({},false) }
    function openBrowserDraft(draft,browse) {
        var s=Object.assign({},backend.settings,draft)
        server.text=s.dav_url; user.text=s.dav_user; password.text=s.password || ""; rclonePath.text=s.rclone
        storage.text=s.cloud_folder; location.text=s.cloud_folder==="/" ? "" : s.cloud_folder
        separateComputer.checked=s.cloud_separate_computer; retryCount.value=s.cloud_retries; timeoutSeconds.value=s.cloud_timeout; watchUpload.checked=s.watch_upload
        var configured=backend.games.findIndex(function(game) { return game.saveSet })
        layoutGame.currentIndex=Math.max(0,configured)
        show(); raise(); requestActivate()
        if(browse!==false && !backend.busy) backend.browseCloud(location.text,values())
    }
    onVisibleChanged: if (!visible) password.text=""
    Connections { target: backend; function onCloudChanged() { location.text=backend.cloudPath } }
    Connections { target: backend; function onDirectoriesChanged() { cloud.selectedName=""; cloud.selectedEntry=({}) } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        RowLayout {
            Label { text: "云端存储"; font.pixelSize: 28; font.bold: true }
            Item { Layout.fillWidth: true }
            Label { text: backend.settings.computer; color: Theme.secondary }
            AppButton { text: "DAV 连接设置"; onClicked: configTabs.currentIndex=1 }
            AppButton { text: "传输选项"; onClicked: configTabs.currentIndex=2 }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 64; radius: 6; color: Theme.surface
            Column {
                anchors.fill: parent; anchors.margins: 11; spacing: 5
                Label { text: "备份位置"; color: Theme.secondary; font.pixelSize: 12 }
                Label { text: backend.settings.dav_url + "  →  " + (backend.settings.cloud_folder || "尚未选择存储文件夹"); width: parent.width; elide: Text.ElideMiddle; font.pixelSize: 16 }
            }
        }
        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 18
            ScrollView {
                id: connectionPane
                Layout.preferredWidth: 280; Layout.maximumWidth: 310; Layout.minimumWidth: 230; Layout.fillHeight: true
                clip: true; contentWidth: availableWidth
                ColumnLayout {
                    width: connectionPane.availableWidth-12; spacing: 8
                    TabBar {
                        id: configTabs; objectName: "cloudConfigTabs"; Layout.fillWidth: true; currentIndex: backend.settings.has_password ? 0 : 1
                        TabButton { text: "存储位置"; font.pixelSize: 13 }
                        TabButton { text: "DAV 连接"; font.pixelSize: 13 }
                        TabButton { text: "传输"; font.pixelSize: 13 }
                    }
                    Label { visible: configTabs.currentIndex===0; text: "备份文件夹"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.bold: true }
                    AppTextField { visible: configTabs.currentIndex===0; id: storage; objectName: "cloudStorage"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "选择右侧浏览中的文件夹" }
                    AppButton { visible: configTabs.currentIndex===0; text: "使用当前浏览文件夹"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: storage.text=backend.cloudPath || "/" }
                    AppButton { visible: configTabs.currentIndex!==1; text: "验证并保存设置"; highlighted: true; Layout.fillWidth: true; enabled: !backend.busy; onClicked: { var v=cloud.values(); v.cloud_folder=storage.text; backend.configureCloud(v) } }
                    Label { visible: configTabs.currentIndex===0; text: "目录结构预览"; font.bold: true }
                    AppComboBox { visible: configTabs.currentIndex===0; id: layoutGame; objectName: "cloudLayoutGame"; Layout.fillWidth: true; model: backend.games; textRole: "name"; valueRole: "id" }
                    Label { visible: configTabs.currentIndex===0; objectName: "cloudLayoutPreview"; text: layoutGame.currentValue ? backend.cloudGamePath(layoutGame.currentValue,cloud.values())+"/备份.zip" : "导入 Playnite 后显示游戏目录"; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.secondary; font.pixelSize: 12 }
                    CheckBox { visible: configTabs.currentIndex===0; id: separateComputer; objectName: "cloudSeparateComputer"; text: "存档目录下按电脑分组"; checked: backend.settings.cloud_separate_computer; Layout.fillWidth: true }
                    Label { visible: configTabs.currentIndex===0; text: "默认按游戏名和存档目录分组，中文名称保留。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
                    ColumnLayout {
                        visible: configTabs.currentIndex===2; Layout.fillWidth: true
                        Label { text: "传输选项"; font.bold: true }
                        RowLayout { Label { text: "失败尝试次数"; Layout.fillWidth: true } CompactSpinBox { id: retryCount; from: 1; to: 3; value: backend.settings.cloud_retries } }
                        RowLayout { Label { text: "超时（秒）"; Layout.fillWidth: true } CompactSpinBox { id: timeoutSeconds; from: 10; to: 120; stepSize: 10; value: backend.settings.cloud_timeout } }
                        CheckBox { id: watchUpload; text: "自动备份后上传"; checked: backend.settings.watch_upload; Layout.fillWidth: true }
                        Label { text: "自动备份需在系统设置中开启游戏监听。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11 }
                    }
                    Label { visible: configTabs.currentIndex===1; text: "连接设置"; font.pixelSize: 18; font.bold: true }
                    Label { visible: configTabs.currentIndex===1; text: "先连接，再在右侧选择云端文件夹。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
                    Label { visible: configTabs.currentIndex===1; text: "WebDAV 地址" }
                    AppTextField { visible: configTabs.currentIndex===1; id: server; objectName: "davServer"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "DAV 地址" }
                    Label { visible: configTabs.currentIndex===1; text: "AList 地址需以 /dav/ 结尾，例如 http://服务器:5244/dav/。请填写 WebDAV 地址，而非网页首页地址。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 11 }
                    Label { visible: configTabs.currentIndex===1; text: "用户名" }
                    AppTextField { visible: configTabs.currentIndex===1; id: user; Layout.fillWidth: true; placeholderText: "用户名"; selectByMouse: true }
                    Label { visible: configTabs.currentIndex===1; text: "密码" }
                    AppTextField { visible: configTabs.currentIndex===1; id: password; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_password ? "密码已保存，留空保持" : "密码" }
                    AppButton { visible: configTabs.currentIndex===1; text: "连接并浏览文件夹"; highlighted: true; enabled: !backend.busy; Layout.fillWidth: true; onClicked: backend.browseCloud("",values()) }
                    AppButton { visible: configTabs.currentIndex===1; id: advanced; text: "高级：rclone 程序位置"; checkable: true; Layout.fillWidth: true }
                    AppTextField { id: rclonePath; visible: configTabs.currentIndex===1 && advanced.checked; Layout.fillWidth: true; selectByMouse: true }
                    AppButton { visible: configTabs.currentIndex===1 && advanced.checked; text: "选择 rclone.exe"; Layout.fillWidth: true; onClicked: { var p=backend.pickFile("exe"); if(p) rclonePath.text=p } }
                    Label { text: "单击文件夹进入，单击文件预览。AList 请进入实际挂载文件夹后选择保存位置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary; font.pixelSize: 12 }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10
                RowLayout {
                    Label { text: "进入要保存备份的文件夹，再点击选择。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
                    AppButton { text: "选择此文件夹"; enabled: !backend.busy && !!backend.cloudPath; onClicked: { storage.text=backend.cloudPath; configTabs.currentIndex=0 } }
                }
                RowLayout {
                    AppButton { text: "上一级"; enabled: !backend.busy; onClicked: backend.browseCloud(backend.cloudPath.split('/').slice(0,-1).join('/'),cloud.values()) }
                    AppTextField { id: location; Layout.fillWidth: true; selectByMouse: true; placeholderText: "DAV 根目录"; onAccepted: backend.browseCloud(text,cloud.values()) }
                    AppButton { text: "前往"; enabled: !backend.busy; onClicked: backend.browseCloud(location.text,cloud.values()) }
                    IconButton { iconName: "refresh"; hint: "刷新当前目录"; enabled: !backend.busy; onClicked: backend.browseCloud(backend.cloudPath,cloud.values()) }
                }
                RowLayout {
                    AppTextField { id: fileSearch; objectName: "cloudFileSearch"; placeholderText: "筛选文件名"; Layout.fillWidth: true }
                    AppComboBox { id: fileSort; objectName: "cloudFileSort"; Layout.preferredWidth: 135; model: ["名称", "最近修改", "文件大小"] }
                    AppButton { text: "新建文件夹"; enabled: !backend.busy; onClicked: { newFolderName.text=""; newFolderDialog.open() } }
                    AppButton { text: "整理旧备份"; enabled: !backend.busy && backend.games.length>0 && backend.directories.some(function(entry) { return !entry.IsDir && /\.zip$/i.test(entry.Name) }); onClicked: organizeDialog.open() }
                }
                RowLayout {
                    CheckBox { id: foldersOnly; objectName: "cloudFoldersOnly"; text: "仅文件夹" }
                    CheckBox { id: showHidden; objectName: "cloudShowHidden"; text: "显示隐藏文件" }
                    Item { Layout.fillWidth: true }
                    AppButton { text: "下载文件"; enabled: !backend.busy && !!cloud.selectedEntry.Name && !cloud.selectedEntry.IsDir; onClicked: backend.downloadCloud(backend.cloudPath,cloud.selectedEntry,cloud.values()) }
                }
                RowLayout {
                    Label { text: "/ " + backend.cloudPath; Layout.fillWidth: true; elide: Text.ElideMiddle; color: Theme.secondary }
                    Label { text: cloud.visibleEntries.length + " 项"; color: Theme.secondary }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: 10; color: Theme.sidebar
                    ListView {
                        id: files; objectName: "davFiles"
                        anchors.fill: parent; anchors.margins: 7; clip: true
                        model: cloud.visibleEntries
                        delegate: ItemDelegate {
                            required property var modelData
                            width: ListView.view.width; height: 53
                            highlighted: cloud.selectedName===modelData.Name
                            contentItem: RowLayout {
                                Image { source: "icons/"+(modelData.IsDir ? "folder" : "file")+".svg"; Layout.preferredWidth: 20; Layout.preferredHeight: 20; sourceSize: Qt.size(60,60) }
                                Label { text: cloud.entryLabel(modelData); Layout.fillWidth: true; elide: Text.ElideRight }
                                Label { text: modelData.IsDir ? "文件夹" : cloud.fileSize(modelData.Size); color: Theme.secondary; font.pixelSize: 11 }
                            }
                            onClicked: { cloud.selectedName=modelData.Name; cloud.selectedEntry=modelData; if(!backend.busy) { if(modelData.IsDir) backend.browseCloud((backend.cloudPath ? backend.cloudPath+"/" : "")+modelData.Name,cloud.values()); else backend.previewCloud(backend.cloudPath,modelData,cloud.values()) } }
                        }
                        ScrollBar.vertical: ScrollBar {}
                        Label { anchors.centerIn: parent; visible: files.count===0; text: backend.busy ? "正在读取…" : backend.directories.length ? "没有符合筛选条件的文件" : "当前目录为空，或尚未连接"; color: Theme.secondary }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: backend.cloudPreview.name ? 190 : 58; radius: 6; color: Theme.sidebar
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 7
                        Label { text: "预览 · "+(backend.cloudPreview.name || "选择一个文件"); font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                        Label { visible: !!backend.cloudPreview.name; text: backend.cloudPreview.name ? (backend.cloudPreview.size>=0 ? cloud.fileSize(backend.cloudPreview.size)+" · " : "")+backend.formatLocalTime(backend.cloudPreview.modified || "") : ""; color: Theme.secondary; font.pixelSize: 11 }
                        RowLayout {
                            visible: !!backend.cloudPreview.name
                            Layout.fillWidth: true; Layout.fillHeight: true
                            Image { visible: !!backend.cloudPreview.image; source: backend.cloudPreview.image || ""; Layout.preferredWidth: 140; Layout.fillHeight: true; fillMode: Image.PreserveAspectFit; asynchronous: true }
                            ScrollView {
                                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                                TextArea { text: backend.cloudPreview.text || backend.cloudPreview.path || ""; readOnly: true; wrapMode: Text.Wrap; selectByMouse: true; font.pixelSize: 12 }
                            }
                        }
                    }
                }
            }
        }
        RowLayout {
            AppBusyIndicator { implicitWidth: 26; implicitHeight: 26; running: backend.busy; visible: running }
            Label { text: backend.status; Layout.fillWidth: true; elide: Text.ElideRight; color: Theme.secondary }
            AppButton { text: "关闭"; onClicked: cloud.close() }
        }
    }
    Dialog {
        id: newFolderDialog; title: "新建文件夹"; anchors.centerIn: parent; width: 420; modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            Label { text: "/"+backend.cloudPath; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: Theme.secondary }
            AppTextField { id: newFolderName; Layout.fillWidth: true; placeholderText: "文件夹名" }
        }
        onAccepted: backend.createCloudFolder(backend.cloudPath,newFolderName.text,cloud.values())
    }
    Dialog {
        id: organizeDialog; title: "整理旧备份"; anchors.centerIn: parent; width: 570; modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            spacing: 12
            Label { text: "来源：/"+backend.cloudPath; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere }
            Label { text: "选择对应的 Playnite 游戏" }
            AppComboBox { id: organizeGame; Layout.fillWidth: true; model: backend.games; textRole: "name"; valueRole: "id" }
            Label { text: "复制到“游戏名 / 存档目录”后核对文件完整性。存档目录从备份读取，旧文件保留原位。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: Theme.secondary }
        }
        onOpened: { var index=backend.games.findIndex(function(game) { return backend.cloudPath.split('/').pop()===game.id }); organizeGame.currentIndex=index>=0 ? index : layoutGame.currentIndex }
        onAccepted: backend.organizeCloud(organizeGame.currentValue,backend.cloudPath,cloud.values())
    }
}
