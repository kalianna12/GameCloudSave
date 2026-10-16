import QtQuick
import QtQuick.Window
Item {
    id: sky
    objectName: "atlasSky"
    property real phase: 0
    property real offsetX: 0
    property real offsetY: 0
    property bool suspended: false
    readonly property bool animated: !suspended && Theme.motion && visible && !!Window.window && Window.window.visible && Window.window.active && backend.watchInfo.running===0
    // Two cached canvases drift as textures. No image downloads, particles or
    // per-frame canvas painting; the slow sky advances at 12.5 Hz while idle.
    Timer { interval: 80; repeat: true; running: sky.animated; onTriggered: sky.phase+=.009 }
    Canvas {
        id: clouds; x: -35+Math.sin(sky.phase*.21)*20+Math.sin(sky.offsetX*.01)*10; y: -30+Math.cos(sky.phase*.17)*16+Math.sin(sky.offsetY*.01)*10; width: sky.width+70; height: sky.height+60
        opacity: .8+Math.sin(sky.phase*.3)*.1
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d");c.clearRect(0,0,width,height)
            var colors=["#244e83","#623d80","#226f79","#2c3e82","#8b5274"]
            for(var i=0;i<9;i++) {
                var x=width*(.1+(i*.271)% .9),y=height*(.12+(i*.193)% .8),r=Math.max(width,height)*(.2+(i%3)*.07)
                var g=c.createRadialGradient(x,y,0,x,y,r);g.addColorStop(0,colors[i%colors.length]);g.addColorStop(.45,Qt.rgba(.12,.18,.34,.28));g.addColorStop(1,"transparent")
                c.globalAlpha=.32;c.fillStyle=g;c.fillRect(0,0,width,height)
            }
            // Soft gas filaments, painted once beneath the drifting star layer.
            for(var j=0;j<8;j++) {
                c.beginPath();c.moveTo(-80,height*(.15+j*.012));c.bezierCurveTo(width*.35,height*(.9-j*.025),width*.58,height*(.05+j*.035),width+80,height*(.7+j*.015))
                c.strokeStyle=j%2 ? "#568597" : "#7e689b";c.lineWidth=12+j*8;c.globalAlpha=.018;c.stroke()
            };c.globalAlpha=1
        }
    }
    Canvas {
        x: Math.sin(sky.phase*.13)*7-8; y: Math.cos(sky.phase*.19)*5-8; width: sky.width+16; height: sky.height+16
        opacity: .76+Math.sin(sky.phase)*.15
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d"),count=Math.floor(width*height/2100);c.clearRect(0,0,width,height)
            function noise(n) { var a=Math.sin(n*127.1+311.7)*43758.5453;return a-Math.floor(a) }
            for(var i=0;i<count;i++) {
                var x=noise(i+1)*width,y=noise(i+389)*height,r=noise(i+743)>.97 ? 1.7 : .45+noise(i+19)*.65
                c.globalAlpha=.25+noise(i+57)*.7;c.fillStyle=i%7===0 ? "#e8cfa3" : "#b9d7ef";c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill()
                if(r>1.5) { c.globalAlpha=.2;c.fillRect(x-4,y-.3,8,.6);c.fillRect(x-.3,y-4,.6,8) }
            };c.globalAlpha=1
        }
    }
}
