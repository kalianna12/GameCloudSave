import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
ApplicationWindow {
    id: batch; width: 1180; height: 800; minimumWidth: 980; minimumHeight: 650
    title: "批量确认存档"; color: Theme.background; font.family: "Microsoft YaHei UI"; Material.theme: Theme.dark ? Material.Dark : Material.Light; Material.accent: Theme.accent
    property var selected: ({})
    property var paths: ({})
    property real savedY: 0
    ListModel { id: stableRows; dynamicRoles: true }
    function syncRows() {
        var data=rows
        for(var i=0;i<data.length;i++) {
            var position=-1
            for(var j=0;j<stableRows.count;j++) if(stableRows.get(j).record.id===data[i].id) { position=j;break }
            if(position<0) stableRows.append({record:data[i]});else stableRows.set(position,{record:data[i]})
        }
        for(var k=stableRows.count-1;k>=0;k--) if(!data.some(function(row) { return row.id===stableRows.get(k).record.id })) stableRows.remove(k)
    }
    property var rows: backend.games.filter(function(game) { return !installed.checked || game.installed }).map(function(game) { return Object.assign({},game,backend.matchResults.find(function(row) { return row.id===game.id }) || {}) })
    function populate() { var next=Object.assign({},paths); rows.forEach(function(row) { if(!next[row.id]) next[row.id]=backend.recommendedMatchPath(row.id) });paths=next }
    function openBatch() { populate();syncRows();show();raise();requestActivate() }
    function choose(ident,path) { var next=Object.assign({},paths);next[ident]=path;paths=next }
    function selectAll() { var next={};rows.forEach(function(row) { if(batch.paths[row.id]) next[row.id]=true });selected=next }
    function ids() { return Object.keys(selected).filter(function(id) { return !!batch.paths[id] && batch.rows.some(function(row) { return row.id===id }) }) }
    function restoreScroll() { Qt.callLater(function() { list.contentY=Math.max(list.originY,Math.min(batch.savedY,Math.max(list.originY,list.contentHeight-list.height))) }) }
    Connections { target: backend; function onGamesChanged() { if(batch.visible) batch.syncRows() } function onMatchesChanged() { if(batch.visible) batch.syncRows() } }
    function confirmed() { return ids().length>0 && ids().every(function(id) { return backend.gameSettings(id).save_dir===batch.paths[id] }) }
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 14
        RowLayout { Label { text: "批量确认存档"; font.pixelSize: 26; font.bold: true } Item { Layout.fillWidth: true } AppButton { text: "关闭"; onClicked: batch.close() } }
        Label { text: "每行选择一个存档目录，无需逐个打开游戏。多候选请核对，未找到时可手动选择。"; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
        RowLayout {
            CheckBox { id: installed; text: "仅已安装"; checked: true; onToggled: { batch.savedY=0;batch.populate();batch.syncRows();batch.restoreScroll() } }
            AppButton { text: "全选有目录的游戏"; enabled: !backend.busy; onClicked: batch.selectAll() }
            AppButton { text: "清除选择"; onClicked: batch.selected=({}) }
            AppButton { text: "刷新建议"; enabled: !backend.busy; onClicked: batch.populate() }
            Item { Layout.fillWidth: true } Label { text: "已选 "+batch.ids().length+" 款"; color: Theme.secondary }
        }
        ListView { id: list; objectName: "batchGameList"; Layout.fillWidth: true; Layout.fillHeight: true; model: stableRows; clip: true; spacing: 4
            onContentYChanged: if(moving || bar.pressed) batch.savedY=contentY
            delegate: ItemDelegate {
                required property var record; property var modelData: record; width: ListView.view.width; height: 80
                property var options: [{path:"",label:"请选择存档目录"}].concat((modelData.candidates || []).map(function(candidate) { return {path:candidate.path,label:candidate.path,score:candidate.confidence} })).concat(batch.paths[modelData.id] && !(modelData.candidates || []).some(function(candidate) { return candidate.path===batch.paths[modelData.id] }) ? [{path:batch.paths[modelData.id],label:"当前 / 手动："+batch.paths[modelData.id]}] : [])
                contentItem: RowLayout {
                    CheckBox { checked: !!batch.selected[modelData.id]; enabled: !backend.busy && !!batch.paths[modelData.id]; onToggled: { var next=Object.assign({},batch.selected);if(checked) next[modelData.id]=true;else delete next[modelData.id];batch.selected=next } }
                    ColumnLayout { Layout.preferredWidth: 210; Layout.minimumWidth: 160
                        Label { text: modelData.name; Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true }
                        Label { text: modelData.status==="applied" ? "已设置" : (modelData.candidates || []).length+" 个候选"; color: Theme.secondary; font.pixelSize: 11 }
                    }
                    ColumnLayout { Layout.fillWidth: true
                        ComboBox { id: picker; implicitHeight: 38; Layout.fillWidth: true; model: options; textRole: "label"; currentIndex: Math.max(0,options.findIndex(function(option) { return option.path===batch.paths[modelData.id] })); onActivated: batch.choose(modelData.id,options[currentIndex].path)
                            contentItem: Label { text: picker.currentText; font.pixelSize: 12; elide: Text.ElideMiddle; verticalAlignment: Text.AlignVCenter; color: Theme.text; leftPadding: 12; rightPadding: 32 }
                            ToolTip.visible: hover.hovered; ToolTip.text: batch.paths[modelData.id] || "请选择目录"; HoverHandler { id: hover }
                        }
                        Label { text: batch.paths[modelData.id] || "尚未选择"; Layout.fillWidth: true; elide: Text.ElideMiddle; font.pixelSize: 11; color: Theme.secondary }
                    }
                    AppButton { text: "手动选择"; enabled: !backend.busy; onClicked: { var path=backend.pickSaveFolder(batch.paths[modelData.id] || ((modelData.candidates || [])[0] || {}).path || backend.gameSettings(modelData.id).install_dir || "");if(path) batch.choose(modelData.id,path) } }
                    ScoreRing { score: ((modelData.candidates || []).find(function(candidate) { return candidate.path===batch.paths[modelData.id] }) || {}).confidence || 0; Layout.preferredWidth: 48; Layout.preferredHeight: 48 }
                }
            }
            ScrollBar.vertical: ScrollBar { id: bar }
            ColumnLayout { visible: list.count===0; anchors.centerIn: parent; spacing: 10
                Label { text: "没有可确认的游戏"; font.pixelSize: 20; font.bold: true; Layout.alignment: Qt.AlignHCenter }
                Label { text: backend.games.length ? "取消“仅已安装”，或先导入本机游戏。" : "先导入游戏并查找存档，再到这里确认目录。"; color: Theme.secondary; wrapMode: Text.Wrap }
            }
        }
        RowLayout {
            AppButton { text: "确认所选目录"; highlighted: true; enabled: !backend.busy && batch.ids().length>0; onClicked: backend.applyMatches(batch.ids().map(function(id) { return {id:id,path:batch.paths[id]} })) }
            AppButton { text: "备份所选到本地"; enabled: !backend.busy && batch.confirmed(); onClicked: backend.backupConfigured(batch.ids(),false) }
            AppButton { text: "备份所选到云端"; enabled: !backend.busy && batch.confirmed() && !!backend.settings.cloud_folder; onClicked: backend.backupConfigured(batch.ids(),true) }
            Item { Layout.fillWidth: true }
        }
        Label { text: backend.status; color: Theme.secondary; Layout.fillWidth: true; wrapMode: Text.Wrap }
    }
}
