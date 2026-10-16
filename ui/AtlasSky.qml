import QtQuick
import QtQuick.Window
Item {
    id: sky
    objectName: "atlasSky"
    property real phase: 0
    property real offsetX: 0
    property real offsetY: 0
    property bool suspended: false
    property int texturePaints: 0
    readonly property bool animated: !suspended && Theme.motion && visible && !!Window.window && Window.window.visible && Window.window.active && backend.watchInfo.running===0
    // Cached clouds/stars plus a small bounded sprite field. Only transforms
    // and opacity change at 12.5 Hz; no per-tick canvas painting.
    Timer { interval: 80; repeat: true; running: sky.animated; onTriggered: sky.phase+=.025 }
    Canvas {
        id: clouds; objectName: "atlasNebulaTexture"
        x: -50+Math.sin(sky.phase*.45)*32+Math.sin(sky.offsetX*.01)*10; y: -50+Math.cos(sky.phase*.35)*25+Math.sin(sky.offsetY*.01)*10
        width: Math.min(1400,sky.width+100); height: Math.min(900,sky.height+100)
        transform: Scale { xScale: (sky.width+100)/Math.max(1,clouds.width); yScale: (sky.height+100)/Math.max(1,clouds.height) }
        opacity: .8+Math.sin(sky.phase*.3)*.1
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        onPaint: {
            sky.texturePaints++
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
        id: distantStars; x: Math.sin(sky.phase*.25)*18-20; y: Math.cos(sky.phase*.32)*14-20
        width: Math.min(1400,sky.width+40); height: Math.min(900,sky.height+40)
        transform: Scale { xScale: (sky.width+40)/Math.max(1,distantStars.width); yScale: (sky.height+40)/Math.max(1,distantStars.height) }
        opacity: .76+Math.sin(sky.phase)*.15
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        onPaint: {
            sky.texturePaints++
            var c=getContext("2d"),count=Math.floor(width*height/2100);c.clearRect(0,0,width,height)
            function noise(n) { var a=Math.sin(n*127.1+311.7)*43758.5453;return a-Math.floor(a) }
            for(var i=0;i<count;i++) {
                var x=noise(i+1)*width,y=noise(i+389)*height,r=noise(i+743)>.97 ? 1.7 : .45+noise(i+19)*.65
                c.globalAlpha=.25+noise(i+57)*.7;c.fillStyle=i%7===0 ? "#e8cfa3" : "#b9d7ef";c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fill()
                if(r>1.5) { c.globalAlpha=.2;c.fillRect(x-4,y-.3,8,.6);c.fillRect(x-.3,y-4,.6,8) }
            };c.globalAlpha=1
        }
    }
    Repeater {
        model: 16
        Item {
            required property int index
            objectName: "atlasDriftingStar-"+index
            readonly property real shimmer: .35+.65*(.5+.5*Math.sin(sky.phase*(1.2+index%3*.2)+index*2.13))
            x: ((index*.273%1)*(sky.width+80)+sky.phase*(9+index%4*7))%(sky.width+80)-40
            y: sky.height*(.08+(index*.177% .84))+Math.sin(sky.phase*.5+index)*12
            width: 12; height: 12; opacity: shimmer
            Rectangle { anchors.centerIn: parent; width: 12; height: 12; radius: 6; color: index%3 ? "#18a6d8ff" : "#18ffe0ac" }
            Rectangle { anchors.centerIn: parent; width: index%4 ? 2 : 3; height: width; radius: width/2; color: index%3 ? "#c6e5ff" : "#ffe7bc" }
            Rectangle { visible: index%4===0; anchors.centerIn: parent; width: 9; height: 1; color: "#65c6e5ff" }
            Rectangle { visible: index%4===0; anchors.centerIn: parent; width: 1; height: 9; color: "#65c6e5ff" }
        }
    }
    Item {
        id: meteor; objectName: "atlasMeteor"
        readonly property real progress: (sky.phase%2.8)/.45
        visible: Theme.motion && progress<1
        x: sky.width*(.08+progress*.65); y: sky.height*(.06+progress*.36)
        width: Math.min(110,sky.width*.18); height: 3
        rotation: Math.atan2(sky.height*.36,sky.width*.65)*180/Math.PI
        opacity: Math.sin(Math.PI*Math.min(1,progress))*.75
        Rectangle { anchors.fill: parent; radius: 2; gradient: Gradient { orientation: Gradient.Horizontal; GradientStop { position: 0; color: "transparent" } GradientStop { position: .8; color: "#6084caff" } GradientStop { position: 1; color: "#e5f4ff" } } }
        Rectangle { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 5; height: 5; radius: 2.5; color: "#e5f4ff" }
    }
}
