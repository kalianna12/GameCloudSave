import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtWebEngine
Item {
    id: browser
    objectName: "inlineImageBrowser"
    property string token: ""
    property string providerId: "google"
    property url searchUrl
    property string message: ""
    signal collected(int count)
    signal dismissed()
    function collect() {
        var currentToken=token,source=providerId
        web.runJavaScript(backend.imageCaptureScript,function(raw) {
            if(!browser || currentToken!==browser.token) return
            var rows=[];try { rows=JSON.parse(raw || "[]") } catch(e) {}
            var accepted=backend.receiveInlineImages(currentToken,source,rows)
            message=accepted ? "已采集图片" : "未找到合适的图片，可在本页点开图片后重新采集"
            if(accepted) Qt.callLater(function() { if(browser && currentToken===browser.token) browser.collected(accepted) })
        })
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 6
        RowLayout {
            Layout.fillWidth: true
            AppButton { text: "返回图片列表"; onClicked: browser.dismissed() }
            AppButton { text: "后退"; enabled: web.canGoBack; onClicked: web.goBack() }
            Label { text: browser.message || (web.loading ? "正在加载搜索页…" : "搜索页"); color: Theme.secondary; Layout.fillWidth: true; elide: Text.ElideRight }
            AppButton { objectName: "collectPageImages"; text: "采集本页图片"; highlighted: true; enabled: !backend.busy; onClicked: browser.collect() }
        }
        ProgressBar { Layout.fillWidth: true; visible: web.loading; value: web.loadProgress/100 }
        WebEngineView {
            id: web; objectName: "imageSearchWebView"; Layout.fillWidth: true; Layout.fillHeight: true
            url: browser.searchUrl; audioMuted: true
            settings.focusOnNavigationEnabled: false
            settings.javascriptCanAccessClipboard: false
            settings.playbackRequiresUserGesture: true
            profile: WebEngineProfile { offTheRecord: true; onDownloadRequested: function(download) { download.cancel() } }
            onNewWindowRequested: function(request) { web.acceptAsNewWindow(request) }
            onNavigationRequested: function(request) { if(!/^(https?:|about:|data:)/i.test(request.url.toString())) request.reject() }
            onLoadingChanged: function(info) {
                if(info.status===WebEngineView.LoadSucceededStatus) captureDelay.restart()
                else if(info.status===WebEngineView.LoadFailedStatus) browser.message="搜索页加载失败，可重新搜索或更换来源"
            }
        }
    }
    Timer { id: captureDelay; interval: 900; onTriggered: if(!backend.busy) browser.collect() }
    function loadFixture(html) { web.loadHtml(html,"https://search.example/") }
    Component.onDestruction: { captureDelay.stop();if(web) web.stop() }
}
