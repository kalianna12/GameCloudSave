import QtQuick
Canvas {
    id: glyph
    property string button: "A"
    property color ink: Theme.text
    property color cutout: Theme.surface
    implicitWidth: button==="LB" || button==="RB" ? 30 : 26
    implicitHeight: 26
    onButtonChanged: requestPaint()
    onInkChanged: requestPaint()
    onCutoutChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c=getContext("2d");c.reset();c.scale(width/30,height/28)
        c.strokeStyle=ink;c.fillStyle=ink;c.lineWidth=1.6;c.lineJoin="round";c.lineCap="round"
        if(button==="LB" || button==="RB") {
            c.beginPath();c.moveTo(2,12);c.quadraticCurveTo(3,5,13,5);c.lineTo(26,5);c.quadraticCurveTo(29,5,29,9);c.lineTo(29,21);c.lineTo(2,21);c.closePath();c.fill()
            c.fillStyle=cutout;c.font="bold 13px sans-serif";c.textAlign="center";c.textBaseline="middle";c.fillText(button,16,14)
        } else if(button==="R3") {
            c.beginPath();c.moveTo(10,1);c.lineTo(20,1);c.lineTo(15,8);c.closePath();c.fill()
            c.fillRect(12,10,6,3);c.fillRect(5,15,20,12)
            c.fillStyle=cutout;c.font="bold 12px sans-serif";c.textAlign="center";c.textBaseline="middle";c.fillText("R",15,22)
        } else if(button==="delete") {
            c.beginPath();c.moveTo(2,14);c.lineTo(11,5);c.lineTo(28,5);c.lineTo(28,23);c.lineTo(11,23);c.closePath();c.stroke()
            c.beginPath();c.moveTo(14,9);c.lineTo(24,19);c.moveTo(24,9);c.lineTo(14,19);c.stroke()
        } else {
            c.beginPath();c.arc(15,14,11,0,Math.PI*2);c.stroke()
            if(button==="Menu") { c.beginPath();for(var i=0;i<3;i++) { c.moveTo(9,10+i*4);c.lineTo(21,10+i*4) };c.stroke() }
            else { c.font="bold 16px sans-serif";c.textAlign="center";c.textBaseline="middle";c.fillText(button,15,14) }
        }
    }
}
