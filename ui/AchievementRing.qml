import QtQuick
import QtQuick.Controls

Item {
    id: ring
    property int completed: 0
    property int total: 0
    readonly property real fraction: total>0 ? Math.max(0,Math.min(1,completed/total)) : 0
    property color tint: fraction>=1 ? (Theme.dark ? "#d9be82" : "#896322") : Theme.accent
    implicitWidth: 86;implicitHeight: 86
    Accessible.name: "成就完成度 "+completed+" / "+total
    Canvas {
        id: circle;anchors.fill: parent
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d"),x=width/2,y=height/2,r=Math.min(x,y)-5
            c.reset();if(r<=0) return
            c.lineWidth=4;c.strokeStyle=Theme.outline.toString();c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.stroke()
            if(ring.fraction>0) { c.lineCap="round";c.strokeStyle=ring.tint.toString();c.beginPath();c.arc(x,y,r,-Math.PI/2,-Math.PI/2+ring.fraction*Math.PI*2);c.stroke() }
        }
        Connections { target: ring;function onFractionChanged() { circle.requestPaint() } function onTintChanged() { circle.requestPaint() } }
        Connections { target: Theme;function onPaletteChanged() { circle.requestPaint() } }
    }
    Column {
        anchors.centerIn: parent;spacing: 2
        Label { anchors.horizontalCenter: parent.horizontalCenter;text: Math.round(ring.fraction*100)+"%";font.pixelSize: 20;font.weight: Font.DemiBold;color: ring.tint }
        Label { anchors.horizontalCenter: parent.horizontalCenter;text: ring.fraction>=1 && ring.total ? "全成就" : "完成度";font.pixelSize: 10;color: Theme.secondary }
    }
}
