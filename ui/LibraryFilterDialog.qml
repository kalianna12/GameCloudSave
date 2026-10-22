import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import "LibraryFilters.js" as Filters
import "ControllerForm.js" as Form
Dialog {
    id: dialog
    objectName: "libraryFilterDialog"
    title: "筛选游戏";modal: true;focus: true
    width: Math.min(620,parent.width-48);height: Math.min(filterFields.implicitHeight+200,parent.height-48)
    Overlay.modal: Rectangle { color: "#99000000" }
    exit: Transition {}
    property var games: []
    property var retained: ({})
    property var catalog: Filters.options(games,retained)
    property string draftSeries: ""
    property string draftYear: ""
    property var draftTags: []
    readonly property var draft: ({series:draftSeries,year:draftYear,tags:draftTags})
    readonly property int resultCount: games.filter(function(game) { return Filters.matches(game,dialog.draft) }).length
    signal criteriaApplied(var values)
    onDraftSeriesChanged: if(seriesChoice) seriesChoice.currentIndex=Math.max(0,seriesChoice.model.indexOf(draftSeries))
    onDraftYearChanged: if(yearChoice) yearChoice.currentIndex=draftYear==="unknown" ? 1 : Math.max(0,yearChoice.model.indexOf(draftYear))
    onCatalogChanged: Qt.callLater(function() { seriesChoice.currentIndex=Math.max(0,seriesChoice.model.indexOf(dialog.draftSeries));yearChoice.currentIndex=dialog.draftYear==="unknown" ? 1 : Math.max(0,yearChoice.model.indexOf(dialog.draftYear)) })
    function begin(values) { retained={series:values.series || "",year:values.year || "",tags:(values.tags || []).slice()};draftSeries=retained.series;draftYear=retained.year;draftTags=retained.tags.slice();open();Qt.callLater(function() { seriesChoice.forceActiveFocus() }) }
    function clearDraft() { draftSeries="";draftYear="";draftTags=[] }
    function apply() { backend.navigationEvent("group",backend.settings.library_design || "classic");criteriaApplied(draft);close() }
    function controls() { var list=[seriesChoice,yearChoice];for(var i=0;i<tagChoices.count;i++) list.push(tagChoices.itemAt(i));return Form.available(list.concat([clearButton,applyButton])) }
    function controllerInput(command) {
        if(command==="back") { close();return true }
        if(command==="menu") { apply();return true }
        if(command==="favorite") { clearDraft();return true }
        var items=controls(),focus=dialog.contentItem.Window.window.activeFocusItem,index=Form.indexOfFocus(items,focus)
        if(index<0) { Form.reveal(items[0],scroll);return true }
        var current=items[index]
        if(command==="activate") { Form.activate(current);return true }
        if((command==="left" || command==="right") && current.popup) return Form.handle(items,focus,command,scroll)
        if(["left","right","up","down"].indexOf(command)<0) return true
        var p=current.mapToItem(dialog.contentItem,current.width/2,current.height/2),best=null,score=Infinity
        items.forEach(function(item) {
            if(item===current) return
            var q=item.mapToItem(dialog.contentItem,item.width/2,item.height/2),dx=q.x-p.x,dy=q.y-p.y
            var distance=command==="left" ? -dx : command==="right" ? dx : command==="up" ? -dy : dy
            var cross=command==="left" || command==="right" ? Math.abs(dy) : Math.abs(dx)
            if(distance<2 || (command==="left" || command==="right") && cross>current.height/2) return
            var value=distance+cross*2;if(value<score) { score=value;best=item }
        })
        if(best) { Form.reveal(best,scroll);backend.navigationMoved() }
        return true
    }
    contentItem: ScrollView {
        id: scroll;clip: true;contentWidth: availableWidth
        ColumnLayout {
            id: filterFields
            width: scroll.availableWidth;spacing: 14
            Label { text: "系列、标签和年份可组合筛选。";color: Theme.secondary;Layout.fillWidth: true;wrapMode: Text.Wrap }
            Label { text: "系列";font.bold: true }
            AppComboBox { id: seriesChoice;objectName: "facetSeriesChoice";soundEvent: "group";Layout.fillWidth: true;model: ["全部系列"].concat(dialog.catalog.series);currentIndex: Math.max(0,model.indexOf(dialog.draftSeries));onActivated: { backend.navigationEvent("group",backend.settings.library_design || "classic");dialog.draftSeries=currentIndex ? currentText : "" } }
            Label { text: "发行年份";font.bold: true }
            AppComboBox { id: yearChoice;objectName: "facetYearChoice";soundEvent: "group";Layout.fillWidth: true;model: ["全部年份","年份未记录"].concat(dialog.catalog.years);currentIndex: dialog.draftYear==="unknown" ? 1 : Math.max(0,model.indexOf(dialog.draftYear));onActivated: { backend.navigationEvent("group",backend.settings.library_design || "classic");dialog.draftYear=currentIndex===1 ? "unknown" : currentIndex>1 ? currentText : "" } }
            Label { text: "标签（匹配其中任一项）";font.bold: true }
            Label { visible: !dialog.catalog.tags.length;text: "游戏库尚未设置标签";color: Theme.secondary }
            GridLayout {
                Layout.fillWidth: true;columns: 3;columnSpacing: 8;rowSpacing: 8
                Repeater {
                    id: tagChoices;model: dialog.catalog.tags
                    AppButton {
                        required property string modelData
                        objectName: "facetTag-"+modelData
                        Layout.fillWidth: true;Layout.minimumWidth: 0
                        checkable: true;checked: dialog.draftTags.indexOf(modelData)>=0
                        text: (checked ? "✓ " : "")+modelData
                        onClicked: dialog.draftTags=checked ? dialog.draftTags.concat([modelData]) : dialog.draftTags.filter(function(tag) { return tag!==modelData })
                    }
                }
            }
        }
    }
    footer: Item {
        implicitHeight: 100
        ColumnLayout {
            anchors.fill: parent;anchors.margins: 12;spacing: 8
            Label { objectName: "filterResultCount";text: "符合条件："+dialog.resultCount+" 款";color: Theme.secondary }
            RowLayout {
                Layout.fillWidth: true
                AppButton { id: clearButton;objectName: "clearFilterDraft";text: "清空条件";onClicked: dialog.clearDraft() }
                Item { Layout.fillWidth: true }
                AppButton { id: applyButton;objectName: "applyLibraryFilters";text: "应用筛选";highlighted: true;onClicked: dialog.apply() }
            }
        }
    }
}
