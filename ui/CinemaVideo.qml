import QtQuick
import QtMultimedia
Item {
    id: video
    property alias source: player.source
    property alias muted: audio.muted
    signal playbackFailed()
    signal finished()
    function stop() { player.stop();player.source="" }
    MediaPlayer {
        id: player; objectName: "cinemaPlayer"; videoOutput: output; audioOutput: audio
        onSourceChanged: if(source.toString()) play()
        onErrorOccurred: video.playbackFailed()
        onMediaStatusChanged: if(mediaStatus===MediaPlayer.EndOfMedia) video.finished()
    }
    AudioOutput { id: audio; muted: true }
    VideoOutput { id: output; objectName: "cinemaOutput"; anchors.fill: parent; fillMode: VideoOutput.PreserveAspectCrop }
    Component.onDestruction: player.stop()
}
