import QtQuick
import QtQuick.Controls
Item {
    id: badge
    objectName: "achievementBadge"
    property string gameId: ""
    readonly property var progress: { var version=backend.achievements.summaryRevision;return backend.achievements.summary(gameId) }
    readonly property int total: progress.total || 0
    readonly property int completed: Math.min(total,progress.unlocked || 0)
    readonly property real fraction: total ? completed/total : 0
    width: 48;height: width+16
    visible: total>0
    z: 9
    Rectangle { anchors.fill: parent;radius: 8;color: "#aa14151d";border.color: "#28ffffff" }
    Canvas {
        id: ring;x: 3;y: 3;width: parent.width-6;height: width
        onPaint: {
            var ctx=getContext("2d"),r=width/2-2
            ctx.reset();ctx.lineWidth=2.6;ctx.strokeStyle="#60ffffff";ctx.beginPath();ctx.arc(width/2,height/2,r,0,2*Math.PI);ctx.stroke()
            if(badge.fraction>0) { ctx.strokeStyle=Theme.accent.toString();ctx.lineCap="round";ctx.beginPath();ctx.arc(width/2,height/2,r,-Math.PI/2,-Math.PI/2+2*Math.PI*badge.fraction);ctx.stroke() }
        }
        onWidthChanged: requestPaint()
        Connections { target: badge;function onFractionChanged() { ring.requestPaint() } }
        Connections { target: Theme;function onAccentChanged() { ring.requestPaint() } }
    }
    Image { source: "icons/achievement-medal.svg";x: (parent.width-width)/2;y: 10;width: parent.width*.48;height: width*56/48;sourceSize.width: 96 }
    Label { objectName: "achievementBadgeCount";anchors.left: parent.left;anchors.right: parent.right;y: parent.width-1;height: 16;text: badge.completed+"/"+badge.total;color: "white";font.pixelSize: 10;font.bold: true;horizontalAlignment: Text.AlignHCenter;verticalAlignment: Text.AlignVCenter }
    Accessible.name: "成就 "+completed+" / "+total
}
