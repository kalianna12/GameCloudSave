import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ColumnLayout {
    id: section
    required property var config
    readonly property var mapper: backend.mapping
    signal editRequested()
    readonly property var targets: ["","P:LY+","P:LY-","P:LX-","P:LX+","P:RY+","P:RY-","P:RX-","P:RX+","custom"]
    spacing: 12
    Label { text: "滚轮控制摇杆";color: Theme.text;font.pixelSize: 17;font.weight: Font.DemiBold }
    Repeater {
        model: ["M:wheelup","M:wheeldown"]
        RowLayout {
            required property string modelData
            Layout.fillWidth: true
            Label { text: section.mapper.label(modelData);color: Theme.secondary;Layout.preferredWidth: 72;font.pixelSize: 13 }
            AppComboBox {
                objectName: "mappingWheel-"+modelData.slice(2);Layout.fillWidth: true
                model: ["未绑定","左摇杆向上","左摇杆向下","左摇杆向左","左摇杆向右","右摇杆向上","右摇杆向下","右摇杆向左","右摇杆向右","自定义组合"]
                currentIndex: { var dependency=section.config.routes;return section.targets.indexOf(section.mapper.wheelTarget(modelData)) }
                onActivated: if(currentIndex<9) section.mapper.setWheelTarget(modelData,section.targets[currentIndex]);else section.mapper.selectSource([modelData])
            }
            AppButton { text: "编辑";onClicked: { section.mapper.selectSource([modelData]);section.editRequested() } }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Label { text: "保持时间（毫秒）";color: Theme.secondary;Layout.fillWidth: true;font.pixelSize: 13 }
        CompactSpinBox { objectName: "mappingWheelPulse";from: 20;to: 500;stepSize: 10;value: section.config.wheelPulse;onValueModified: section.mapper.setOption("reverse","wheelPulse",value) }
    }
}
