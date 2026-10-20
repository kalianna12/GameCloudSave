import QtQuick
import QtQuick.Controls
Item {
    id: pad
    property var selectedTokens: []
    property var sample: ({})
    property bool reverse: false
    property string modelType: "xbox"
    readonly property bool artworkReady: xboxArt.status===Image.Ready && psArt.status===Image.Ready && joyArt.status===Image.Ready
    signal chosen(string token)
    signal assigned(string source,string target)
    implicitHeight: 390
    function buttonLabel(name) {
        if(modelType==="ps") return ({A:"×",B:"○",X:"□",Y:"△",LB:"L1",RB:"R1",LT:"L2",RT:"R2",LS:"L3",RS:"R3",Back:"Create",Start:"Options"})[name] || name
        if(modelType==="joycon") return ({A:"B",B:"A",X:"Y",Y:"X",LB:"L",RB:"R",LT:"ZL",RT:"ZR",Back:"−",Start:"+"})[name] || name
        return ({Back:"▢",Start:"☰"})[name] || name
    }
    readonly property var placements: {
        var ps=modelType==="ps",joy=modelType==="joycon"
        var ls=ps ? [295,380] : joy ? [260,240] : [190,290]
        var rs=ps ? [525,380] : joy ? [560,420] : [525,430]
        var d=ps ? [195,275] : joy ? [260,410] : [285,430]
        var f=ps ? [630,275] : joy ? [560,250] : [640,290]
        var list=[{id:"LS",x:ls[0],y:ls[1],w:100,h:100,kind:"stick"},{id:"RS",x:rs[0],y:rs[1],w:100,h:100,kind:"stick"}]
        ;[["Y",0,-40],["X",-40,0],["B",40,0],["A",0,40]].forEach(function(v) { list.push({id:v[0],x:f[0]+v[1],y:f[1]+v[2],w:43,h:43,kind:"face"}) })
        ;[["DUp",0,-35],["DLeft",-35,0],["DRight",35,0],["DDown",0,35]].forEach(function(v) { list.push({id:v[0],x:d[0]+v[1],y:d[1]+v[2],w:joy ? 27 : 38,h:joy ? 27 : 38,kind:"direction"}) })
        var lx=joy ? 260 : 220,rx=joy ? 560 : 600
        list.push({id:"LT",x:lx,y:55,w:50,h:74,kind:"trigger"},{id:"RT",x:rx,y:55,w:50,h:74,kind:"trigger"},
                  {id:"LB",x:lx,y:118,w:80,h:29,kind:"shoulder"},{id:"RB",x:rx,y:118,w:80,h:29,kind:"shoulder"},
                  {id:"Back",x:ps ? 245 : joy ? 290 : 348,y:ps ? 208 : joy ? 167 : 295,w:32,h:32,kind:"utility"},
                  {id:"Start",x:ps ? 575 : joy ? 530 : 470,y:ps ? 208 : joy ? 167 : 295,w:32,h:32,kind:"utility"})
        return list
    }
    Item {
        id: stage
        width: Math.min(pad.width,pad.height*820/650);height: width*650/820;anchors.centerIn: parent
        readonly property real s: width/820
        Image {
            id: xboxArt;objectName: "mappingBodyImageXbox";anchors.fill: parent;sourceSize.width: 1024
            source: "assets/mapping-xbox.svg";asynchronous: true;cache: true;visible: pad.modelType==="xbox"
        }
        Image {
            id: psArt;objectName: "mappingBodyImagePS";anchors.fill: parent;sourceSize.width: 1024
            source: "assets/mapping-ps.svg";asynchronous: true;cache: true;visible: pad.modelType==="ps"
        }
        Image {
            id: joyArt;objectName: "mappingBodyImageJoycon";anchors.fill: parent;sourceSize.width: 1024
            source: "assets/mapping-joycon.svg";asynchronous: true;cache: true;visible: pad.modelType==="joycon"
        }
        Repeater {
            model: 16
            MappingKey {
                id: button
                required property int index
                property var modelData: pad.placements[index]
                x: (modelData.x-modelData.w/2)*stage.s;y: (modelData.y-modelData.h/2)*stage.s
                width: modelData.w*stage.s;height: modelData.h*stage.s;surfaceVisible: false
                token: "P:"+modelData.id;label: pad.buttonLabel(modelData.id)
                selected: pad.selectedTokens.some(function(t) { return t===button.token || modelData.kind==="stick" && t.indexOf(button.token+".")===0 })
                pressedLive: (pad.sample.buttons || []).indexOf(modelData.id)>=0
                property bool stick: modelData.kind==="stick"
                property color faceRing: pad.modelType==="xbox" && modelData.kind==="face" ? ({A:"#84c997",B:"#ed9fa1",X:"#9bbcf7",Y:"#ebd27a"})[modelData.id] : "#d5d2cf"
                Rectangle {
                    anchors.fill: parent;radius: button.stick || ["face","utility"].indexOf(modelData.kind)>=0 || pad.modelType==="joycon" ? width/2 : modelData.kind==="trigger" ? 20*stage.s : 8*stage.s
                    color: button.pressedLive || button.dropHovered ? Theme.accent : button.stick ? pad.modelType==="joycon" ? "#27474a" : "#e7e5e2" : modelData.kind==="direction" && pad.modelType!=="joycon" ? "transparent" : "#efeeec"
                    border.width: button.selected || button.dropHovered ? 4*stage.s : modelData.kind==="direction" ? 0 : 3*stage.s
                    border.color: button.selected || button.dropHovered ? Theme.accent : button.faceRing
                    Rectangle {
                        visible: button.stick;anchors.centerIn: parent;width: parent.width*.77;height: width;radius: width/2
                        transform: Translate { x: ((pad.sample[modelData.id] || [0,0])[0])*8*stage.s;y: -((pad.sample[modelData.id] || [0,0])[1])*8*stage.s }
                        color: pad.modelType==="joycon" ? "#292d30" : pad.modelType==="ps" ? "#fafafa" : "#d2cfcb";border.width: (pad.modelType==="ps" ? 9 : 4)*stage.s;border.color: pad.modelType==="joycon" ? "#1f6b72" : pad.modelType==="ps" ? "#797570" : "#c4c0bb"
                        Rectangle { visible: pad.modelType==="xbox";anchors.centerIn: parent;width: parent.width*.37;height: width;radius: width/2;color: "#bebbb6" }
                    }
                    Label {
                        visible: !button.stick;anchors.centerIn: parent;text: modelData.kind==="direction" ? "" : modelData.kind==="utility" && pad.modelType==="ps" ? (modelData.id==="Back" ? "•" : "≡") : button.label
                        font.pixelSize: (modelData.kind==="face" ? 23 : modelData.kind==="utility" ? 18 : 16)*stage.s;font.bold: true
                        color: button.pressedLive ? Theme.onAccent : "#a6a29d"
                    }
                }
                onChosen: function(token) { pad.chosen(token) }
                onAssigned: function(source,target) { pad.assigned(source,target) }
            }
        }
    }
    Row {
        visible: pad.reverse;anchors.bottom: parent.bottom;anchors.horizontalCenter: parent.horizontalCenter;spacing: 4
        Repeater {
            model: ["LX-","LX+","LY+","LY-","RX-","RX+","RY+","RY-"]
            MappingKey {
                required property string modelData
                width: 42;height: 28;token: "P:"+modelData;label: ({"LX-":"L←","LX+":"L→","LY+":"L↑","LY-":"L↓","RX-":"R←","RX+":"R→","RY+":"R↑","RY-":"R↓"})[modelData];selected: pad.selectedTokens.indexOf(token)>=0
                onChosen: function(token) { pad.chosen(token) }
                onAssigned: function(source,target) { pad.assigned(source,target) }
            }
        }
    }
}
