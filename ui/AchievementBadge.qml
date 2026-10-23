import QtQuick
import QtQuick.Controls
Item {
    id: badge
    objectName: "achievementBadge"
    property string gameId: ""
    property bool revealed: false
    readonly property var progress: { var version=backend.achievements.summaryRevision;return backend.achievements.summary(gameId) }
    readonly property int total: progress.total || 0
    readonly property int completed: Math.min(total,progress.unlocked || 0)
    readonly property real fraction: total ? completed/total : 0
    readonly property color ringColor: fraction>=1 ? "#f2cc73" : fraction<=0 ? "#92a0b4" : fraction<.5 ? blend("#7f9fce","#55c8c4",fraction*2) : blend("#55c8c4","#83d28a",(fraction-.5)*2)
    function blend(a,b,t) {
        var first=Qt.color(a),last=Qt.color(b)
        return Qt.rgba(first.r+(last.r-first.r)*t,first.g+(last.g-first.g)*t,first.b+(last.b-first.b)*t,1)
    }
    width: 48;height: width+16
    visible: total>0 && (Theme.achievementBadgeMode==="always" || Theme.achievementBadgeMode==="hover" && revealed)
    z: 9
    Rectangle { anchors.fill: parent;radius: 8;color: "#aa14151d";border.color: "#28ffffff" }
    Canvas {
        id: ring;x: 3;y: 3;width: parent.width-6;height: width
        onPaint: {
            var ctx=getContext("2d"),r=width/2-2
            ctx.reset();ctx.lineWidth=2.6;ctx.strokeStyle=badge.fraction ? "#50ffffff" : badge.ringColor.toString();ctx.beginPath();ctx.arc(width/2,height/2,r,0,2*Math.PI);ctx.stroke()
            if(badge.fraction>0) { ctx.strokeStyle=badge.ringColor.toString();ctx.lineCap="round";ctx.beginPath();ctx.arc(width/2,height/2,r,-Math.PI/2,-Math.PI/2+2*Math.PI*badge.fraction);ctx.stroke() }
        }
        onWidthChanged: requestPaint()
        Connections {
            target: badge
            function onFractionChanged() { ring.requestPaint() }
            function onVisibleChanged() { if(badge.visible) ring.requestPaint() }
        }
    }
    Image { source: "icons/achievement-medal.svg";x: (parent.width-width)/2;y: 10;width: parent.width*.48;height: width*56/48;sourceSize.width: 96 }
    Label { objectName: "achievementBadgeCount";anchors.left: parent.left;anchors.right: parent.right;y: parent.width-1;height: 16;text: badge.completed+"/"+badge.total;color: "white";font.pixelSize: 10;font.bold: true;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter }
    Accessible.name: "成就 "+completed+" / "+total
}
