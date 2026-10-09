import QtQuick
import QtQuick.Controls
Item {
    id: ring
    property real score: 0
    property int percentage: Math.round(Math.max(0,Math.min(1,score))*100)
    implicitWidth: 64; implicitHeight: 64
    Canvas {
        id: ringCanvas
        anchors.fill: parent
        onPaint: {
            var ctx=getContext("2d"); ctx.reset()
            var center=width/2, radius=Math.min(width,height)/2-5
            ctx.lineWidth=4; ctx.lineCap="round"
            ctx.strokeStyle=Theme.border; ctx.beginPath(); ctx.arc(center,height/2,radius,0,2*Math.PI); ctx.stroke()
            if(ring.percentage>0) {
                ctx.strokeStyle=Theme.dark ? "#80c942" : "#397b17"; ctx.beginPath()
                ctx.arc(center,height/2,radius,-Math.PI/2,-Math.PI/2+2*Math.PI*ring.percentage/100); ctx.stroke()
            }
        }
        Connections { target: ring; function onPercentageChanged() { ringCanvas.requestPaint() } }
        Connections { target: Theme; function onBorderChanged() { ringCanvas.requestPaint() } }
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }
    Label { anchors.centerIn: parent; text: ring.percentage; font.pixelSize: 19; font.bold: true; color: Theme.text }
    Accessible.name: "匹配评分 "+percentage+" / 100"
}
