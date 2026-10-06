import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: cloud
    width: 1180; height: 820; minimumWidth: 920; minimumHeight: 680
    title: "云端存储 · DAV 文件浏览"
    color: "#111a14"; Material.theme: Material.Dark; Material.accent: "#8ce34f"
    font.family: "Microsoft YaHei UI"
    property string selectedName: ""
    function fileSize(bytes) { return bytes<1024 ? bytes+" B" : bytes<1048576 ? (bytes/1024).toFixed(1)+" KB" : (bytes/1048576).toFixed(1)+" MB" }
    function values() { return {dav_url:server.text,dav_user:user.text,password:password.text,rclone:rclonePath.text} }
    function openBrowser() {
        var s=backend.settings
        server.text=s.dav_url; user.text=s.dav_user; password.text=""; rclonePath.text=s.rclone
        storage.text=s.cloud_folder; location.text=s.cloud_folder==="/" ? "" : s.cloud_folder
        show(); raise(); requestActivate()
        if(!backend.busy) backend.browseCloud(location.text,values())
    }
    onVisibleChanged: if (!visible) password.text=""
    Connections { target: backend; function onCloudChanged() { location.text=backend.cloudPath } }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        RowLayout {
            Label { text: "云端存储"; font.pixelSize: 28; font.bold: true }
            Item { Layout.fillWidth: true }
            Label { text: backend.settings.computer; color: "#8faa97" }
        }
        Rectangle {
            Layout.fillWidth: true; Layout.preferredHeight: 80; radius: 12; color: "#213d29"
            Column {
                anchors.fill: parent; anchors.margins: 15; spacing: 8
                Label { text: "当前保存位置 · 所有游戏自动分目录"; color: "#a3ce93"; font.pixelSize: 12 }
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
                    Label { text: "① 连接 → ② 选目录 → ③ 验证保存"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#b4e0a0"; font.bold: true }
                    TextField { id: storage; objectName: "cloudStorage"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "选择右侧浏览中的文件夹" }
                    Button { text: "使用当前浏览文件夹"; Layout.fillWidth: true; enabled: !backend.busy; onClicked: storage.text=backend.cloudPath || "/" }
                    Button { text: "验证读写权限并保存"; highlighted: true; Layout.fillWidth: true; enabled: !backend.busy; onClicked: { var v=cloud.values(); v.cloud_folder=storage.text; backend.configureCloud(v) } }
                    Rectangle { Layout.fillWidth: true; height: 1; color: "#35483b" }
                    Label { text: "连接设置"; font.pixelSize: 18; font.bold: true }
                    TextField { id: server; objectName: "davServer"; Layout.fillWidth: true; selectByMouse: true; placeholderText: "DAV 地址" }
                    TextField { id: user; Layout.fillWidth: true; placeholderText: "用户名"; selectByMouse: true }
                    TextField { id: password; Layout.fillWidth: true; echoMode: TextInput.Password; placeholderText: backend.settings.has_password ? "密码已保存，留空保持" : "密码" }
                    Button { text: "测试连接 / 浏览根目录"; enabled: !backend.busy; Layout.fillWidth: true; onClicked: backend.browseCloud("",values()) }
                    Button { id: advanced; text: "高级：rclone 程序位置"; checkable: true; Layout.fillWidth: true }
                    TextField { id: rclonePath; visible: advanced.checked; Layout.fillWidth: true; selectByMouse: true }
                    Button { visible: advanced.checked; text: "选择 rclone.exe"; Layout.fillWidth: true; onClicked: { var p=backend.pickFile("exe"); if(p) rclonePath.text=p } }
                    Label { text: "单击文件夹进入，单击文件预览。AList 请进入实际挂载文件夹后选择保存位置。"; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#879e8e"; font.pixelSize: 12 }
                }
            }
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 10
                RowLayout {
                    Button { text: "上一级"; enabled: !backend.busy; onClicked: backend.browseCloud(backend.cloudPath.split('/').slice(0,-1).join('/'),cloud.values()) }
                    TextField { id: location; Layout.fillWidth: true; selectByMouse: true; placeholderText: "DAV 根目录"; onAccepted: backend.browseCloud(text,cloud.values()) }
                    Button { text: "前往"; enabled: !backend.busy; onClicked: backend.browseCloud(location.text,cloud.values()) }
                }
                RowLayout {
                    Label { text: "/ " + backend.cloudPath; Layout.fillWidth: true; elide: Text.ElideMiddle; color: "#a4d991" }
                    Label { text: backend.directories.length + " 项"; color: "#8ca491" }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; radius: 10; color: "#1a281e"
                    ListView {
                        id: files; objectName: "davFiles"
                        anchors.fill: parent; anchors.margins: 7; clip: true
                        model: backend.directories
                        delegate: ItemDelegate {
                            required property var modelData
                            width: ListView.view.width; height: 53
                            highlighted: cloud.selectedName===modelData.Name
                            contentItem: RowLayout {
                                Label { text: modelData.IsDir ? "▸" : "▤"; font.pixelSize: 22; color: modelData.IsDir ? "#a5df78" : "#a7bdb0"; Layout.preferredWidth: 24 }
                                Label { text: modelData.Name; Layout.fillWidth: true; elide: Text.ElideRight }
                                Label { text: modelData.IsDir ? "文件夹" : cloud.fileSize(modelData.Size); color: "#91a798"; font.pixelSize: 11 }
                            }
                            onClicked: { cloud.selectedName=modelData.Name; if(!backend.busy) { if(modelData.IsDir) backend.browseCloud((backend.cloudPath ? backend.cloudPath+"/" : "")+modelData.Name,cloud.values()); else backend.previewCloud(backend.cloudPath,modelData,cloud.values()) } }
                        }
                        ScrollBar.vertical: ScrollBar {}
                        Label { anchors.centerIn: parent; visible: files.count===0; text: backend.busy ? "正在读取…" : "当前目录为空，或尚未连接"; color: "#8aa18f" }
                    }
                }
                Rectangle {
                    Layout.fillWidth: true; Layout.preferredHeight: 190; radius: 10; color: "#1a281e"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 7
                        Label { text: "预览 · "+(backend.cloudPreview.name || "选择一个文件"); font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight }
                        Label { text: backend.cloudPreview.name ? (backend.cloudPreview.size>=0 ? cloud.fileSize(backend.cloudPreview.size)+" · " : "")+(backend.cloudPreview.modified || "") : "支持文本与小图片预览，其他文件显示详细信息"; color: "#93ad9a"; font.pixelSize: 11 }
                        RowLayout {
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
            BusyIndicator { implicitWidth: 26; implicitHeight: 26; running: backend.busy; visible: running }
            Label { text: backend.status; Layout.fillWidth: true; elide: Text.ElideRight; color: "#aac4a6" }
            Button { text: "关闭"; onClicked: cloud.close() }
        }
    }
}
