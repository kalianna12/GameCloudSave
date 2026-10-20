import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: panel
    required property string stickId
    required property string zone
    required property var config
    readonly property var mapper: backend.mapping
    signal assigned(string source,string target)
    objectName: "mappingStick-"+zone
    implicitHeight: body.implicitHeight+32
    color: Theme.surface;radius: 12;border.color: Theme.outline
    function names(tokens) { return (tokens || []).map(function(t) { return mapper.label(t) }).join(" + ") || "未绑定" }
    function presetIndex() {
        var sets=[["W","D","S","A"],["↑","→","↓","←"]],directions=["N","NE","E","SE","S","SW","W","NW"]
        for(var p=0;p<sets.length;p++) {
            var v=sets[p],expected=[[v[0]],[v[0],v[1]],[v[1]],[v[2],v[1]],[v[2]],[v[2],v[3]],[v[3]],[v[0],v[3]]]
            if(directions.every(function(d,i) { return names(config[zone][d])===expected[i].join(" + ") })) return p+1
        }
        return 0
    }
    ColumnLayout {
        id: body;anchors.fill: parent;anchors.margins: 16;spacing: 12
        RowLayout {
            Layout.fillWidth: true
            Label { text: panel.zone==="light" ? "轻推" : "重推";font.pixelSize: 17;font.weight: Font.DemiBold;color: Theme.text }
            Item { Layout.fillWidth: true }
            AppComboBox {
                objectName: "mappingPreset-"+panel.zone;Layout.preferredWidth: 140
                model: ["自定义","WASD","方向键"];currentIndex: panel.presetIndex()
                onActivated: if(currentIndex>0) panel.mapper.applyStickPreset(panel.stickId,panel.zone,currentIndex===1 ? "wasd" : "arrows")
            }
        }
        GridLayout {
            Layout.fillWidth: true;columns: 3;rowSpacing: 6;columnSpacing: 6
            Repeater {
                model: ["NW","N","NE","W","","E","SW","S","SE"]
                MappingKey {
                    required property string modelData
                    Layout.fillWidth: true;Layout.minimumWidth: 0;Layout.preferredHeight: 54
                    enabled: !!modelData;opacity: modelData ? 1 : 0
                    token: modelData ? "P:"+panel.stickId+"."+panel.zone+"."+modelData : ""
                    label: ({N:"↑",NE:"↗",E:"→",SE:"↘",S:"↓",SW:"↙",W:"←",NW:"↖"})[modelData] || ""
                    bindingText: modelData ? panel.names(panel.config[panel.zone][modelData]) : ""
                    description: modelData ? panel.mapper.label(token)+"："+bindingText : ""
                    selected: panel.mapper.target===token.slice(2)
                    onChosen: function(token) { panel.mapper.selectTarget(token.slice(2)) }
                    onAssigned: function(source,target) { panel.assigned(source,target) }
                }
            }
        }
        MappingKey {
            Layout.fillWidth: true;Layout.preferredHeight: 38
            token: "P:"+panel.stickId+"."+panel.zone+"Extra"
            label: "附加键："+panel.names(panel.config[panel.zone+"Extra"])
            description: panel.mapper.label(token)+"："+panel.names(panel.config[panel.zone+"Extra"])
            selected: panel.mapper.target===token.slice(2)
            onChosen: function(token) { panel.mapper.selectTarget(token.slice(2)) }
            onAssigned: function(source,target) { panel.assigned(source,target) }
        }
    }
}
