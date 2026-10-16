import QtQuick
import "WoodMaterials.js" as Wood
Rectangle {
    id: surface
    property string species: "walnut"
    property int seed: 1
    property bool vertical: false
    readonly property var wood: Wood.material(species)
    color: wood.base
    // Bounded cached grain: redraw on size/material changes, never per frame.
    Canvas {
        id: grain; objectName: "woodGrain"
        width: Math.min(surface.width,1600); height: Math.min(surface.height,440)
        transform: Scale { xScale: surface.width/Math.max(1,grain.width); yScale: surface.height/Math.max(1,grain.height) }
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        Connections { target: surface; function onSpeciesChanged() { grain.requestPaint() } function onSeedChanged() { grain.requestPaint() } }
        onPaint: {
            var c=getContext("2d"),w=width,h=height;c.clearRect(0,0,w,h);if(!w || !h) return
            c.save();if(surface.vertical) { c.translate(w,0);c.rotate(Math.PI/2);var swap=w;w=h;h=swap }
            function noise(n) { var a=Math.sin(n*127.1+surface.seed*31.7)*43758.5453;return a-Math.floor(a) }
            var wash=c.createLinearGradient(0,0,0,h);wash.addColorStop(0,surface.wood.light);wash.addColorStop(.35,surface.wood.base);wash.addColorStop(1,surface.wood.dark)
            c.fillStyle=wash;c.fillRect(0,0,w,h)
            for(var i=0;i<70;i++) {
                var y=noise(i+3)*h,amplitude=(2+noise(i+8)*7)*(surface.species==="oak" ? 1.5 : 1)
                c.beginPath();c.moveTo(-10,y)
                for(var x=0;x<=w+20;x+=24) c.lineTo(x,y+Math.sin(x/(70+noise(i+17)*130)+i)*amplitude+Math.sin(x*.012+i)*2)
                c.strokeStyle=i%4===0 ? surface.wood.edge : surface.wood.grain;c.globalAlpha=.08+noise(i+35)*.17;c.lineWidth=i%9===0 ? 1.5 : .45;c.stroke()
            }
            // A few elongated pores/knot rings prevent perfectly uniform stripes.
            for(var k=0;k<2;k++) {
                var cx=w*(.23+noise(k+90)*.58),cy=h*(.18+noise(k+95)*.6)
                for(var r=0;r<5;r++) { c.save();c.translate(cx,cy);c.scale(3.4,1);c.beginPath();c.arc(0,0,2+r*2.4,0,Math.PI*2);c.strokeStyle=surface.wood.grain;c.globalAlpha=.10-r*.012;c.lineWidth=.6;c.stroke();c.restore() }
            }
            c.restore();c.globalAlpha=1
        }
    }
}
