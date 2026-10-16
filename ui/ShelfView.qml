import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
Item {
    id: cabinet
    property var groups: []
    property string selectedId: ""
    property bool spines: false
    property int coverSize: 176
    property int currentRow: 0
    property bool controllerFocused: false
    readonly property real bookWidth: Math.max(120,Math.min(230,coverSize*.9))
    readonly property real rowHeight: bookWidth*1.42+166
    readonly property int selectedIndex: currentRow<groups.length ? groups[currentRow].items.findIndex(function(g) { return g.id===selectedId }) : -1
    signal selected(string ident)
    signal detailsRequested(var game)
    function resetPosition() { currentRow=0;shelves.positionViewAtBeginning() }
    function reveal() {
        if(!groups.length) return
        if(currentRow>=groups.length || !groups[currentRow].items.some(function(g) { return g.id===selectedId })) {
            for(var i=0;i<groups.length;i++) if(groups[i].items.some(function(g) { return g.id===selectedId })) { currentRow=i;break }
        }
        shelves.positionViewAtIndex(currentRow,ListView.Contain)
        var row=shelves.itemAtIndex(currentRow);if(row) row.reveal()
    }
    onSelectedIdChanged: Qt.callLater(reveal)
    onGroupsChanged: { currentRow=0;Qt.callLater(reveal) }
    function navigate(direction) {
        if(!groups.length) return false
        var r=currentRow,i=Math.max(0,selectedIndex),step=direction==="left" || direction==="up" ? -1 : 1
        if(direction==="left" || direction==="right") {
            if(i+step<0) return false
            i=Math.min(groups[r].items.length-1,i+step)
        } else {
            if(r+step<0) return false
            r=Math.min(groups.length-1,r+step);i=Math.min(i,groups[r].items.length-1)
        }
        currentRow=r;selected(groups[r].items[i].id);reveal();return true
    }
    function page(direction) {
        if(!groups.length) return
        var i=Math.max(0,Math.min(groups[currentRow].items.length-1,selectedIndex+direction*Math.max(1,Math.floor(width/(spines ? 76 : bookWidth+22)))))
        selected(groups[currentRow].items[i].id);reveal()
    }
    Rectangle { anchors.fill: parent; radius: 8; color: Qt.tint(Theme.background,"#103c1d07") }
    // Recessed vertical cabinet walls; each shelf renders its own grain and lip.
    Repeater { model: 2; Rectangle { required property int index; x: index===0 ? 0 : cabinet.width-10; width: 10; height: cabinet.height; color: "#513825"; Rectangle { width: 2; height: parent.height; color: "#997c50"; opacity: .5 } } }
    ListView {
        id: shelves; objectName: "physicalShelves"; anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 12
        clip: true; model: cabinet.groups; cacheBuffer: cabinet.rowHeight; spacing: 0
        ScrollBar.vertical: ScrollBar { }
        delegate: Item {
            id: row
            required property var modelData; required property int index
            width: shelves.width; height: cabinet.rowHeight
            function reveal() { var i=modelData.items.findIndex(function(g) { return g.id===cabinet.selectedId });if(i>=0) books.positionViewAtIndex(i,ListView.Contain) }
            Rectangle { x: 0; y: 36; width: parent.width; height: parent.height-42; gradient: Gradient { GradientStop { position: 0; color: "#600e0803" } GradientStop { position: 1; color: "#003a2615" } } }
            RowLayout {
                x: 20; y: 4; width: parent.width-40; height: 28
                Label { text: row.modelData.name; color: Theme.text; font.pixelSize: 16; font.weight: Font.DemiBold }
                Label { text: row.modelData.items.length+" 款"; color: Theme.secondary; font.pixelSize: 12 }
                Item { Layout.fillWidth: true }
                IconButton { iconName: "arrow-left"; bare: true; width: 30; height: 28; hint: "向左翻页"; enabled: books.contentX>1; onClicked: books.contentX=Math.max(0,books.contentX-books.width*.9) }
                IconButton { iconName: "arrow-right"; bare: true; width: 30; height: 28; hint: "向右翻页"; enabled: books.contentX+books.width<books.contentWidth-1; onClicked: books.contentX=Math.min(books.contentWidth-books.width,books.contentX+books.width*.9) }
            }
            Rectangle {
                objectName: "shelfPlank"; x: 0; y: cabinet.bookWidth*1.42+92; width: parent.width; height: 38; color: "#735035"
                gradient: Gradient { GradientStop { position: 0; color: "#a67c51" } GradientStop { position: .18; color: "#805836" } GradientStop { position: 1; color: "#493020" } }
                Repeater { model: 5; Rectangle { required property int index; x: 0; y: 3+index*3; width: parent.width; height: 1; color: index%2 ? "#258b5d38" : "#30d5ac70" } }
                Rectangle { anchors.top: parent.bottom; width: parent.width; height: 8; color: "#35000000" }
            }
            ListView {
                id: books; objectName: "books-"+row.index
                x: 18; y: 44; width: parent.width-36; height: parent.height-44
                model: row.modelData.items; orientation: ListView.Horizontal; spacing: cabinet.spines ? 9 : 12
                clip: true; cacheBuffer: 240; reuseItems: true
                delegate: BookCover {
                    required property var modelData; required property int index
                    width: implicitWidth; height: books.height; game: modelData; coverWidth: cabinet.bookWidth; spines: cabinet.spines
                    selected: cabinet.controllerFocused && cabinet.selectedId===modelData.id; suspended: books.moving || shelves.moving
                    onChosen: { cabinet.currentRow=row.index;cabinet.selected(modelData.id) }
                    onOpened: cabinet.detailsRequested(modelData)
                }
                WheelHandler { target: null; onWheel: function(event) { if(event.angleDelta.x || event.modifiers & Qt.ShiftModifier) books.contentX=Math.max(0,Math.min(books.contentWidth-books.width,books.contentX-(event.angleDelta.x || event.angleDelta.y)));else shelves.contentY=Math.max(0,Math.min(shelves.contentHeight-shelves.height,shelves.contentY-event.angleDelta.y));event.accepted=true } }
            }
        }
    }
}
