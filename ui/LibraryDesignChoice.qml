import QtQuick
import QtQuick.Controls
AbstractButton {
    id: choice
    property var design: ({palette:{}})
    property bool selected: false
    implicitHeight: 170; implicitWidth: 260
    hoverEnabled: !backend.controllerMode
    Accessible.name: design.name+"，"+design.detail+(selected ? "，当前设计" : "")
    background: Rectangle { radius: Theme.radius; color: Theme.surface; border.width: choice.selected || choice.activeFocus ? 2 : 1; border.color: choice.selected || choice.activeFocus ? Theme.accent : choice.hovered ? Theme.secondary : Theme.outline }
    contentItem: Item {
        Rectangle {
            id: miniature; x: 10; y: 10; width: parent.width-20; height: 96; clip: true
            color: choice.design.palette.background || Theme.background; radius: 5
            readonly property color ink: choice.design.palette.accent || Theme.accent
            Rectangle { x: 6; y: 6; width: 18; height: parent.height-12; color: choice.design.palette.sidebar || Theme.sidebar }
            Item {
                visible: choice.design.id==="classic"; x: 30; y: 8; width: parent.width-38; height: 80
                Repeater { model: 6; Rectangle { required property int index; x: index%3*parent.width/3; y: Math.floor(index/3)*42; width: parent.width/3-6; height: 36; radius: 2; color: Qt.tint(choice.design.palette.surface,Qt.rgba(miniature.ink.r,miniature.ink.g,miniature.ink.b,.13+index*.08)) } }
            }
            Item {
                visible: choice.design.id==="shelf"; x: 30; y: 6; width: parent.width-38; height: 84
                Repeater { model: 2; Rectangle { required property int index; y: 34+index*44; width: parent.width; height: 7; color: "#986b45" } }
                Repeater { model: 8; Rectangle { required property int index; x: 8+index%4*(parent.width-16)/4; y: Math.floor(index/4)*44; width: (parent.width-40)/4; height: 33; radius: 1; rotation: index===2 ? -5 : 0; color: Qt.tint(choice.design.palette.surface,Qt.rgba(miniature.ink.r,miniature.ink.g,miniature.ink.b,.22+index*.07)); Rectangle { width: 3; height: parent.height; color: "#70000000" } } }
            }
            Item {
                visible: choice.design.id==="cinema"; x: 30; y: 6; width: parent.width-38; height: 84
                Rectangle { anchors.fill: parent; color: "#3a2e44"; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "#17111e" } GradientStop { position: 1; color: "#8c708d" } } }
                Rectangle { x: 8; y: 27; width: parent.width*.48; height: 6; color: "#e8d7ec" }
                Rectangle { x: 8; y: 39; width: 26; height: 4; color: miniature.ink }
                Repeater { model: 5; Rectangle { required property int index; x: 5+index*(parent.width-10)/5; y: 63; width: (parent.width-10)/5-4; height: 17; color: index===1 ? miniature.ink : "#7c6584" } }
            }
            Canvas {
                visible: choice.design.id==="atlas"; x: 30; y: 6; width: parent.width-38; height: 84
                onWidthChanged: requestPaint()
                onPaint: {
                    var c=getContext("2d"),points=[[.15,.38],[.3,.2],[.38,.68],[.62,.38],[.82,.62],[.8,.18]]
                    c.clearRect(0,0,width,height);c.strokeStyle="#607e9d";c.lineWidth=1
                    points.forEach(function(p,i) { if(i) { c.beginPath();c.moveTo(points[i-1][0]*width,points[i-1][1]*height);c.lineTo(p[0]*width,p[1]*height);c.stroke() } })
                    points.forEach(function(p,i) { c.beginPath();c.fillStyle=i===3 ? "#b9ddff" : "#6e97c0";c.arc(p[0]*width,p[1]*height,i===3 ? 8 : 4,0,Math.PI*2);c.fill() })
                }
            }
        }
        Label { x: 12; y: 116; text: choice.design.name; color: Theme.text; font.pixelSize: 15; font.weight: Font.DemiBold }
        Label { x: 12; y: 141; text: choice.design.detail; color: Theme.secondary; font.pixelSize: 11; width: parent.width-24; elide: Text.ElideRight }
        Label { anchors.right: parent.right; anchors.rightMargin: 12; y: 115; text: "✓"; color: Theme.accent; visible: choice.selected }
    }
}
