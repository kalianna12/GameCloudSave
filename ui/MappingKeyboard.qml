import QtQuick
import QtQuick.Controls
Item {
    id: keyboard
    property var selectedTokens: []
    property var pressedTokens: []
    signal chosen(string token)
    signal assigned(string source,string target)
    readonly property real unit: (width-32)/23.5
    readonly property real rowUnit: (height-32)/6.5
    readonly property var keys: makeKeys()
    implicitHeight: unit*6.5+32
    function makeKeys() {
        var list=[]
        function add(vk,x,y,w,h,label,sub) { list.push({vk:vk,x:x,y:y,w:w || 1,h:h || 1,label:label || "",sub:sub || ""}) }
        add(27,0,0,1,1,"Esc")
        for(var i=0;i<12;i++) add(112+i,2+i+Math.floor(i/4)*.5,0,1,1,"F"+(i+1))
        add(44,15.5,0,1,1,"PrtSc");add(145,16.5,0,1,1,"ScrLk");add(19,17.5,0,1,1,"Pause")
        var rows=[
            [[192,1,"~","`"],[49,1,"!","1"],[50,1,"@","2"],[51,1,"#","3"],[52,1,"$","4"],[53,1,"%","5"],[54,1,"^","6"],[55,1,"&","7"],[56,1,"*","8"],[57,1,"(","9"],[48,1,")","0"],[189,1,"_","−"],[187,1,"+","="],[8,2,"Backspace"]],
            [[9,1.5,"Tab"],[81],[87],[69],[82],[84],[89],[85],[73],[79],[80],[219,1,"{","["],[221,1,"}","]"],[220,1.5,"|","\\"]],
            [[20,1.75,"Caps Lock"],[65],[83],[68],[70],[71],[72],[74],[75],[76],[186,1,":",";"],[222,1,"\"","'"],[13,2.25,"Enter"]],
            [[160,2.25,"Shift"],[90],[88],[67],[86],[66],[78],[77],[188,1,"<",","],[190,1,">","."],[191,1,"?","/"],[161,2.75,"Shift"]],
            [[162,1.25,"Ctrl"],[91,1.25,"Win"],[164,1.25,"Alt"],[32,6.25,""],[165,1.25,"Alt"],[92,1.25,"Win"],[93,1.25,"Menu"],[163,1.25,"Ctrl"]]
        ]
        rows.forEach(function(row,index) { var x=0;row.forEach(function(key) { add(key[0],x,index+1.5,key[1] || 1,1,key[2],key[3]);x+=key[1] || 1 }) })
        ;[[45,"Ins"],[36,"Home"],[33,"PgUp"]].forEach(function(key,i) { add(key[0],15.5+i,1.5,1,1,key[1]) })
        ;[[46,"Del"],[35,"End"],[34,"PgDn"]].forEach(function(key,i) { add(key[0],15.5+i,2.5,1,1,key[1]) })
        add(38,16.5,4.5,1,1,"↑");add(37,15.5,5.5,1,1,"←");add(40,16.5,5.5,1,1,"↓");add(39,17.5,5.5,1,1,"→")
        ;[[144,"Num"],[111,"/"],[106,"*"],[109,"−"]].forEach(function(key,i) { add(key[0],19.5+i,1.5,1,1,key[1]) })
        for(var r=0;r<3;r++) for(var c=0;c<3;c++) add(103-r*3+c,19.5+c,2.5+r,1,1,""+(7-r*3+c))
        add(107,22.5,2.5,1,2,"+");add(13,22.5,4.5,1,2,"Enter");add(96,19.5,5.5,2,1,"0");add(110,21.5,5.5,1,1,".")
        return list
    }
    Rectangle { anchors.fill: parent; color: "#1a1e23"; radius: 16; border.color: "#414851" }
    Repeater {
        model: keyboard.keys
        MappingKey {
            required property var modelData
            x: 16+modelData.x*keyboard.unit; y: 16+modelData.y*keyboard.rowUnit
            width: modelData.w*keyboard.unit-3; height: modelData.h*keyboard.rowUnit-3
            keyboardCap: true; token: "K:"+modelData.vk
            label: modelData.label || (modelData.vk===32 ? "" : backend.mapping.label(token)); subLabel: modelData.sub
            selected: keyboard.selectedTokens.indexOf(token)>=0; pressedLive: keyboard.pressedTokens.indexOf(token)>=0
            onChosen: function(token) { keyboard.chosen(token) }
            onAssigned: function(source,target) { keyboard.assigned(source,target) }
        }
    }
}
