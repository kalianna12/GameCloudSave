import QtQuick
import QtQuick.Controls

Rectangle {
    id: chart
    property string kind: "donut"
    property string title: ""
    property var values: []
    property var labels: []
    property string centerText: ""
    property string caption: ""
    property bool compact: false
    property bool semanticColors: false
    property int hoveredIndex: -1
    property real reveal: 1
    property string dataSignature: ""
    readonly property var colors: [Theme.accent,"#70b9d3","#8c95cc","#d4ae73","#8a939f"]
    implicitWidth: 220;implicitHeight: 170
    color: Theme.surface;radius: Theme.radius;border.color: Theme.outline
    function refresh(force) {
        if(!visible) return
        var signature=JSON.stringify(values)
        if(!force && signature===dataSignature) return
        dataSignature=signature
        hoveredIndex=-1
        if(Theme.motion) { reveal=0;appear.restart() } else { reveal=1;plot.requestPaint() }
    }
    onValuesChanged: refresh(false)
    onVisibleChanged: if(visible) refresh(true);else appear.stop()
    onRevealChanged: plot.requestPaint()
    onHoveredIndexChanged: plot.requestPaint()
    NumberAnimation { id: appear;target: chart;property: "reveal";to: 1;duration: 320;easing.type: Easing.OutCubic }
    Label { id: heading;x: 16;y: 12;width: parent.width-32;text: chart.title;font.pixelSize: 13;font.bold: true;color: Theme.text;elide: Text.ElideRight }
    Canvas {
        id: plot;objectName: "achievementChartCanvas";x: 12;y: 38;width: Math.max(0,parent.width-24);height: Math.max(0,parent.height-72)
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        onPaint: {
            var c=getContext("2d"),w=width,h=height,v=chart.values || [],max=Math.max.apply(null,[1].concat(v)),n=v.length
            c.reset();if(w<10 || h<10) return
            c.font="10px Microsoft YaHei UI";c.fillStyle=Theme.secondary.toString();c.strokeStyle=Theme.outline.toString();c.lineWidth=1
            if(chart.kind==="donut") {
                var radius=Math.max(4,Math.min(h*.4,w*.24)),cx=w*.36,cy=h/2,total=v.reduce(function(a,b){return a+b},0),start=-Math.PI/2
                c.lineWidth=Math.max(7,radius*.25);c.strokeStyle=Theme.border.toString();c.beginPath();c.arc(cx,cy,radius,0,Math.PI*2);c.stroke()
                for(var d=0;d<n;d++) {
                    var angle=total ? v[d]/total*Math.PI*2*chart.reveal : 0
                    c.strokeStyle=d===0 ? Theme.accent.toString() : Theme.dark ? "#4d5764" : "#c3ccd5";c.beginPath();c.arc(cx,cy,radius,start,start+angle);c.stroke();start+=angle
                }
                c.textAlign="left";c.font="11px Microsoft YaHei UI"
                for(var j=0;j<Math.min(2,n);j++) { c.fillStyle=j===0 ? Theme.accent.toString() : Theme.secondary.toString();c.fillRect(w*.68,cy-18+j*25,5,5);c.fillText((j===0 ? "已解锁 " : "未解锁 ")+v[j],w*.68+12,cy-11+j*25) }
                return
            }
            var left=28,right=w-8,top=12,bottom=h-27,pw=right-left,ph=bottom-top
            for(var tick=0;tick<3;tick++) {
                if(tick===1 && max<2) continue
                var yy=top+ph*tick/2;c.strokeStyle=Theme.outline.toString();c.beginPath();c.moveTo(left,yy);c.lineTo(right,yy);c.stroke()
                c.fillStyle=Theme.secondary.toString();c.textAlign="right";c.fillText(String(Math.round(max*(1-tick/2))),left-6,yy+3)
            }
            if(chart.kind==="bar") {
                var cell=pw/Math.max(1,n),bw=Math.min(34,cell*.55)
                for(var i=0;i<n;i++) {
                    var x=left+i*cell+(cell-bw)/2,bh=ph*v[i]/max*chart.reveal
                    c.fillStyle=i===chart.hoveredIndex ? Theme.text.toString() : chart.semanticColors ? chart.colors[i%chart.colors.length].toString() : Qt.rgba(Theme.accent.r,Theme.accent.g,Theme.accent.b,.45+.55*(n-i)/Math.max(1,n)).toString();c.fillRect(x,bottom-bh,bw,bh)
                    c.fillStyle=Theme.secondary.toString();c.textAlign="center";var label=String(chart.labels[i] || "");c.fillText(label.length>7 ? label.slice(0,6)+"…" : label,x+bw/2,bottom+17)
                    if(v[i]>0) c.fillText(String(v[i]),x+bw/2,bottom-bh-5)
                }
            } else if(n) {
                c.strokeStyle=Theme.accent.toString();c.lineWidth=2.5;c.beginPath()
                for(var k=0;k<n;k++) { var xx=left+pw*k/Math.max(1,n-1),y=bottom-ph*v[k]/max*chart.reveal;if(k) c.lineTo(xx,y);else c.moveTo(xx,y) };c.stroke()
                c.lineTo(right,bottom);c.lineTo(left,bottom);c.closePath();c.fillStyle=Qt.rgba(Theme.accent.r,Theme.accent.g,Theme.accent.b,.09).toString();c.fill()
                c.fillStyle=Theme.secondary.toString()
                c.textAlign="left";c.fillText(String(chart.labels[0] || ""),left,bottom+17);c.textAlign="right";c.fillText(String(chart.labels[n-1] || ""),right,bottom+17)
                if(chart.hoveredIndex>=0) { var a=chart.hoveredIndex,px=left+pw*a/Math.max(1,n-1),py=bottom-ph*v[a]/max*chart.reveal;c.fillStyle=Theme.text.toString();c.beginPath();c.arc(px,py,4,0,Math.PI*2);c.fill() }
            }
        }
        HoverHandler {
            enabled: chart.kind!=="donut" && chart.values.length>0
            onPointChanged: if(hovered) { var position=(point.position.x-28)/Math.max(1,plot.width-36);chart.hoveredIndex=Math.max(0,Math.min(chart.values.length-1,chart.kind==="bar" ? Math.floor(position*chart.values.length) : Math.round(position*(chart.values.length-1)))) }
            onHoveredChanged: if(!hovered) chart.hoveredIndex=-1
        }
    }
    Column {
        visible: chart.kind==="donut";x: plot.x+plot.width*.36-width/2;y: plot.y+plot.height/2-height/2;spacing: 3
        Label { anchors.horizontalCenter: parent.horizontalCenter;text: chart.centerText;font.pixelSize: Math.max(13,Math.min(24,plot.height*.17));font.weight: Font.DemiBold;color: Theme.text }
        Label { anchors.horizontalCenter: parent.horizontalCenter;visible: plot.height>100;text: "完成度";font.pixelSize: 11;color: Theme.secondary }
    }
    Label { anchors.centerIn: plot;visible: chart.kind!=="donut" && !(chart.values || []).some(function(v) { return v>0 });text: "暂无可展示的解锁记录";font.pixelSize: 11;color: Theme.secondary }
    Label { x: 16;anchors.bottom: parent.bottom;anchors.bottomMargin: 10;width: parent.width-32;font.pixelSize: 11;color: Theme.secondary;elide: Text.ElideRight;text: chart.hoveredIndex>=0 ? (chart.labels[chart.hoveredIndex] || "")+"："+chart.values[chart.hoveredIndex] : chart.caption }
    Connections { target: Theme;function onPaletteChanged() { plot.requestPaint() } function onMotionChanged() { if(!Theme.motion) { appear.stop();chart.reveal=1 } } }
}
