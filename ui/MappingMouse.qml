import QtQuick
import QtQuick.Controls
Item {
    id: mouse
    property var selectedTokens: []
    property var pressedTokens: []
    signal chosen(string token)
    signal assigned(string source,string target)
    implicitHeight: 70
    Rectangle {
        x: 0; y: 4; width: 42; height: 60; radius: 20; color: Theme.surface; border.color: Theme.outline
        Rectangle { x: 20; y: 0; width: 1; height: 27; color: Theme.outline }
        Rectangle { x: 17; y: 10; width: 8; height: 17; radius: 4; color: Theme.secondary }
    }
    Row {
        x: 52; y: 16; spacing: 4
        Repeater {
            model: [{id:"left",name:"左键"},{id:"right",name:"右键"},{id:"middle",name:"中键"},{id:"x1",name:"侧键1"},{id:"x2",name:"侧键2"},{id:"wheelup",name:"滚轮↑"},{id:"wheeldown",name:"滚轮↓"}]
            MappingKey {
                required property var modelData
                width: (mouse.width-80)/7; height: 34; token: "M:"+modelData.id; label: modelData.name
                selected: mouse.selectedTokens.indexOf(token)>=0
                pressedLive: mouse.pressedTokens.indexOf(token)>=0
                onChosen: function(token) { mouse.chosen(token) }
                onAssigned: function(source,target) { mouse.assigned(source,target) }
            }
        }
    }
}
