import QtQuick
Item {
    id: backdrop
    property url source
    property var preloadSources: []
    property int front: 0
    readonly property bool hasFrame: (front===0 ? first.status : second.status)===Image.Ready && !!(front===0 ? first.source : second.source).toString()
    property bool failed: false
    readonly property bool ready: (front===0 ? first.status : second.status)===Image.Ready && (front===0 ? first.source : second.source).toString()===source.toString()
    function requestSource() {
        if(!source.toString()) { first.source="";second.source="";return }
        var nextIndex=front===0 ? 1 : 0,next=nextIndex===1 ? second : first
        next.source=source
        if(next.status===Image.Ready) front=nextIndex
    }
    onSourceChanged: { failed=false;if(!source.toString()) { delay.stop();first.source="";second.source="" } else delay.restart() }
    function loadFailed() { failed=true;first.source="";second.source="" }
    Timer { id: delay; interval: 45; onTriggered: backdrop.requestSource() }
    Image {
        id: first; objectName: "cinemaBackground0"; anchors.fill: parent; asynchronous: true; cache: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 1280
        opacity: backdrop.front===0 ? .8 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motion ? 120 : 0 } }
        onStatusChanged: { if(source.toString()!==backdrop.source.toString()) return;if(status===Image.Ready) backdrop.front=0;else if(status===Image.Error) backdrop.loadFailed() }
    }
    Image {
        id: second; objectName: "cinemaBackground1"; anchors.fill: parent; asynchronous: true; cache: true; fillMode: Image.PreserveAspectCrop; sourceSize.width: 1280
        opacity: backdrop.front===1 ? .8 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motion ? 120 : 0 } }
        onStatusChanged: { if(source.toString()!==backdrop.source.toString()) return;if(status===Image.Ready) backdrop.front=1;else if(status===Image.Error) backdrop.loadFailed() }
    }
    Repeater { model: backdrop.preloadSources; Image { required property string modelData; visible: false; source: modelData; sourceSize.width: 1280; asynchronous: true; cache: true } }
}
