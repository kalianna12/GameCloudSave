import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "AchievementStyle.js" as Style

ItemDelegate {
    id: entry
    required property var record
    property bool revealHidden: false
    property bool selected: false
    property bool compact: false
    hoverEnabled: !backend.controllerMode
    padding: 12;leftPadding: 16;rightPadding: 16
    implicitHeight: Math.max(compact ? 78 : 88,details.implicitHeight+24)
    Accessible.name: Style.title(record,revealHidden)+"，"+(record.unlocked ? "已解锁" : "未解锁")+"，"+Style.rarity(record)
    background: Rectangle {
        color: entry.selected ? Theme.selection : entry.hovered ? Theme.hover : "transparent"
        radius: Theme.controlRadius
        border.color: entry.selected || entry.activeFocus ? Theme.accent : "transparent"
        Rectangle { x: 0;y: 14;width: 3;height: parent.height-28;radius: 2;color: Theme.accent;visible: !!entry.record.unlocked }
        Rectangle { anchors.bottom: parent.bottom;anchors.left: parent.left;anchors.right: parent.right;anchors.leftMargin: 16;anchors.rightMargin: 16;height: 1;color: Theme.outline;visible: !entry.selected }
    }
    contentItem: RowLayout {
        spacing: 14
        Rectangle {
            Layout.preferredWidth: entry.compact ? 50 : 58;Layout.preferredHeight: width;radius: 6;color: Theme.sidebar
            Label { anchors.centerIn: parent;text: entry.record.hidden && !entry.record.unlocked && !entry.revealHidden ? "?" : entry.record.unlocked ? "✓" : "◇";font.pixelSize: 25;color: entry.record.unlocked ? Theme.accent : Theme.secondary;visible: icon.status!==Image.Ready || !icon.visible }
            Image { id: icon;anchors.fill: parent;anchors.margins: 2;source: entry.record.iconUrl || "";sourceSize.width: 128;asynchronous: true;fillMode: Image.PreserveAspectFit;visible: !entry.record.hidden || !!entry.record.unlocked || entry.revealHidden;opacity: entry.record.unlocked ? 1 : .65 }
        }
        ColumnLayout {
            id: details;Layout.fillWidth: true;spacing: 5
            Label { text: Style.title(entry.record,entry.revealHidden);textFormat: Text.PlainText;font.pixelSize: 14;font.weight: Font.DemiBold;Layout.fillWidth: true;elide: Text.ElideRight }
            Label { text: Style.description(entry.record,entry.revealHidden);textFormat: Text.PlainText;Layout.fillWidth: true;wrapMode: Text.Wrap;color: Theme.secondary;font.pixelSize: 12;maximumLineCount: 2;elide: Text.ElideRight }
            RowLayout {
                visible: entry.record.max>0 && !entry.record.unlocked;Layout.fillWidth: true;spacing: 12
                ProgressBar { Layout.fillWidth: true;from: 0;to: Math.max(1,entry.record.max || 0);value: entry.record.progress || 0;implicitHeight: 4 }
                Label { text: (entry.record.progress || 0)+" / "+(entry.record.max || 0);font.pixelSize: 11;color: Theme.secondary }
            }
        }
        ColumnLayout {
            Layout.maximumWidth: entry.width<520 ? 100 : 150;spacing: 6
            Label { Layout.fillWidth: true;horizontalAlignment: Text.AlignRight;text: entry.record.unlocked ? "已解锁" : "未解锁";color: entry.record.unlocked ? Theme.accent : Theme.secondary;font.pixelSize: 11 }
            Label { visible: !!entry.record.unlocked && entry.width>=520;text: entry.record.unlocked_at || "时间未知";color: Theme.secondary;font.pixelSize: 10 }
            Label { Layout.fillWidth: true;horizontalAlignment: Text.AlignRight;text: Style.rarity(entry.record)+(Style.known(entry.record) ? " "+Number(entry.record.rarity).toFixed(1)+"%" : "");color: Style.color(entry.record,Theme.secondary,Theme.dark);font.pixelSize: 10 }
        }
    }
}
