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
        // All positions use the same 820 x 650 coordinates as the SVG shells.
        // Front controls follow the photo proportions; the rear controls are exploded above.
        var ls=ps ? [293,340] : joy ? [253,267] : [236,263]
        var rs=ps ? [527,340] : joy ? [568,391] : [500,370]
        var d=ps ? [192,251] : joy ? [253,389] : [321,375]
        var f=ps ? [628,251] : joy ? [568,267] : [585,266]
        var stickSize=joy ? 76 : 92,faceSize=joy ? 30 : ps ? 43 : 44
        var faceStep=joy ? 32 : ps ? 43 : 44,dirStep=joy ? 32 : 35
        var list=[{id:"LS",x:ls[0],y:ls[1],w:stickSize,h:stickSize,kind:"stick"},{id:"RS",x:rs[0],y:rs[1],w:stickSize,h:stickSize,kind:"stick"}]
        ;[["Y",0,-1],["X",-1,0],["B",1,0],["A",0,1]].forEach(function(v) { list.push({id:v[0],x:f[0]+v[1]*faceStep,y:f[1]+v[2]*faceStep,w:faceSize,h:faceSize,kind:"face"}) })
        ;[["DUp",0,-1],["DLeft",-1,0],["DRight",1,0],["DDown",0,1]].forEach(function(v) { list.push({id:v[0],x:d[0]+v[1]*dirStep,y:d[1]+v[2]*dirStep,w:joy ? 29 : 34,h:joy ? 29 : 34,kind:"direction"}) })
        var lx=joy ? 253 : 220,rx=joy ? 568 : 600
        list.push({id:"LT",x:lx,y:60,w:joy ? 90 : ps ? 54 : 50,h:joy ? 28 : ps ? 56 : 74,kind:"trigger"},{id:"RT",x:rx,y:60,w:joy ? 90 : ps ? 54 : 50,h:joy ? 28 : ps ? 56 : 74,kind:"trigger"},
                  {id:"LB",x:lx,y:joy ? 111 : ps ? 112 : 120,w:ps ? 104 : joy ? 90 : 80,h:ps || joy ? 24 : 29,kind:"shoulder"},{id:"RB",x:rx,y:joy ? 111 : ps ? 112 : 120,w:ps ? 104 : joy ? 90 : 80,h:ps || joy ? 24 : 29,kind:"shoulder"},
                  {id:"Back",x:ps ? 248 : joy ? 294 : 360,y:ps ? 188 : joy ? 197 : 264,w:ps ? 22 : joy ? 26 : 32,h:joy ? 18 : 32,kind:"utility"},
                  {id:"Start",x:ps ? 572 : joy ? 524 : 464,y:ps ? 188 : joy ? 197 : 264,w:ps ? 22 : joy ? 26 : 32,h:joy ? 26 : 32,kind:"utility"})
        return list
    }
    Item {
        id: stage;objectName: "mappingPadArtwork"
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
                description: backend.mapping.label(token)
                token: "P:"+modelData.id;label: pad.buttonLabel(modelData.id)
                selected: pad.selectedTokens.some(function(t) { return t===button.token || modelData.kind==="stick" && t.indexOf(button.token+".")===0 })
                pressedLive: (pad.sample.buttons || []).indexOf(modelData.id)>=0
                property bool stick: modelData.kind==="stick"
                readonly property bool rear: modelData.kind==="trigger" || modelData.kind==="shoulder"
                readonly property bool openSurface: modelData.kind==="direction" && pad.modelType!=="joycon" || modelData.kind==="utility" && pad.modelType==="joycon"
                readonly property bool darkCap: button.stick || button.rear && pad.modelType!=="xbox" || modelData.kind==="face" && pad.modelType!=="ps" || modelData.kind==="direction" && pad.modelType==="joycon"
                readonly property point capVector: {
                    var values=pad.sample[modelData.id] || [0,0],length=Math.max(1,Math.sqrt(values[0]*values[0]+values[1]*values[1]))
                    return Qt.point(values[0]/length,values[1]/length)
                }
                readonly property color faceInk: pad.modelType==="xbox" && modelData.kind==="face" ? ({A:"#8bc34a",B:"#ed747c",X:"#53c2e9",Y:"#e6d96b"})[modelData.id] : modelData.kind==="utility" && pad.modelType==="joycon" ? "#252c35" : button.darkCap ? "#d8dce1" : "#737c88"
                Rectangle {
                    visible: button.rear;z: -1;x: stage.s;y: 4*stage.s;width: parent.width;height: parent.height;radius: modelData.kind==="trigger" ? 16*stage.s : 7*stage.s;color: "#48000000"
                }
                Rectangle {
                    id: cap;objectName: "mappingCap-"+modelData.id
                    anchors.fill: parent;radius: button.stick || modelData.kind==="face" || pad.modelType==="joycon" && modelData.kind==="direction" || pad.modelType==="xbox" && modelData.kind==="utility" ? width/2 : modelData.kind==="trigger" ? 16*stage.s : 7*stage.s
                    readonly property bool lit: button.pressedLive || button.dropHovered
                    color: lit ? Theme.accent : button.openSurface ? "transparent" : button.darkCap ? "#23282f" : "#f1f2f4"
                    gradient: button.openSurface || lit ? null : bevel
                    Gradient {
                        id: bevel
                        GradientStop { position: 0;color: button.darkCap ? "#454c56" : "#ffffff" }
                        GradientStop { position: .34;color: button.darkCap ? "#282e36" : "#f1f3f6" }
                        GradientStop { position: 1;color: button.darkCap ? "#14181e" : "#dce0e5" }
                    }
                    border.width: button.selected || button.dropHovered ? 3*stage.s : button.openSurface ? 0 : 2*stage.s
                    border.color: button.selected || button.dropHovered ? Theme.accent : button.darkCap ? "#666d76" : "#bec4cd"
                    Rectangle {
                        objectName: "mappingStickTop-"+modelData.id
                        visible: button.stick;anchors.centerIn: parent;width: parent.width*.77;height: width;radius: width/2
                        transform: Translate { x: button.capVector.x*button.width*.08;y: -button.capVector.y*button.height*.08 }
                        gradient: Gradient { GradientStop { position: 0;color: "#484f58" } GradientStop { position: .5;color: "#2d333b" } GradientStop { position: 1;color: "#1b2027" } }
                        border.width: 3*stage.s;border.color: "#626a75"
                        Rectangle { anchors.fill: parent;anchors.margins: 5*stage.s;radius: width/2;color: "transparent";border.width: stage.s;border.color: "#343b45" }
                    }
                    Label {
                        visible: !button.stick && !(modelData.kind==="utility" && pad.modelType==="ps") && !(modelData.id==="Back" && pad.modelType==="xbox")
                        anchors.centerIn: parent;text: modelData.kind==="direction" ? pad.modelType==="joycon" ? ({DUp:"▲",DDown:"▼",DLeft:"◀",DRight:"▶"})[modelData.id] : "" : button.label
                        font.pixelSize: (modelData.kind==="face" ? pad.modelType==="joycon" ? 17 : 26 : modelData.kind==="direction" ? 12 : modelData.kind==="utility" ? 20 : 15)*stage.s;font.bold: true
                        color: button.pressedLive ? Theme.onAccent : modelData.kind==="direction" ? "#7f8895" : button.faceInk
                    }
                    Item {
                        visible: modelData.id==="Back" && pad.modelType==="xbox"
                        anchors.centerIn: parent;width: 16*stage.s;height: 14*stage.s
                        Rectangle { x: 0;y: 0;width: 11*stage.s;height: 9*stage.s;radius: stage.s;color: "transparent";border.width: 1.5*stage.s;border.color: button.pressedLive ? Theme.onAccent : button.faceInk }
                        Rectangle { x: 5*stage.s;y: 5*stage.s;width: 11*stage.s;height: 9*stage.s;radius: stage.s;color: button.pressedLive ? Theme.accent : "#f1f3f6";border.width: 1.5*stage.s;border.color: button.pressedLive ? Theme.onAccent : button.faceInk }
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
