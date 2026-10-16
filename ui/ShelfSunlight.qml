import QtQuick
Item {
    id: light
    objectName: "shelfSunlight"
    Canvas {
        id: rays; width: Math.min(light.width,1600); height: Math.min(light.height,900)
        transform: Scale { xScale: light.width/Math.max(1,rays.width); yScale: light.height/Math.max(1,rays.height) }
        onWidthChanged: requestPaint();onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d"),w=width,h=height;c.clearRect(0,0,w,h)
            // Window light travels diagonally across the cabinet and shelf lip.
            for(var i=0;i<3;i++) {
                var x=w*(.55+i*.14),beam=w*.115
                c.save();c.transform(1,0,-.38,1,x,0)
                var g=c.createLinearGradient(0,0,beam,0);g.addColorStop(0,"transparent");g.addColorStop(.13,"#0affe8b3");g.addColorStop(.5,"#20ffdfa0");g.addColorStop(.88,"#12ffdc98");g.addColorStop(1,"transparent")
                c.fillStyle=g;c.fillRect(0,0,beam,h);c.restore()
            }
            var pool=c.createRadialGradient(w*.62,h*.92,0,w*.62,h*.92,w*.29);pool.addColorStop(0,"#20ffe6ba");pool.addColorStop(1,"transparent");c.fillStyle=pool;c.fillRect(0,h*.8,w,h*.2)
        }
    }
}
