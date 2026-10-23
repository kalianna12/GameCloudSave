import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: hero
    property var game: ({})
    property var info: ({})
    property bool compact: false
    implicitHeight: compact ? 94 : 116
    color: Theme.sidebar;radius: Theme.radius
    RowLayout {
        anchors.fill: parent;anchors.margins: 12;spacing: 14
        Rectangle {
            Layout.preferredWidth: hero.compact ? 52 : 64;Layout.fillHeight: true;radius: 4;color: Theme.surface;clip: true
            Image { id: cover;anchors.fill: parent;source: hero.game.coverHighUrl || hero.game.coverUrl || "";asynchronous: true;sourceSize.width: 180;fillMode: Image.PreserveAspectCrop }
            Image { anchors.centerIn: parent;width: 30;height: 36;source: "icons/achievement-medal.svg";visible: cover.status!==Image.Ready;opacity: .6 }
        }
        ColumnLayout {
            Layout.fillWidth: true;spacing: 7
            Label { text: hero.game.name || "游戏成就";textFormat: Text.PlainText;font.pixelSize: hero.compact ? 18 : 21;font.weight: Font.DemiBold;Layout.fillWidth: true;maximumLineCount: 2;wrapMode: Text.Wrap;elide: Text.ElideRight }
            Label { text: (hero.info.unlocked || 0)+" / "+(hero.info.total || 0)+" 已解锁";color: Theme.accent;font.pixelSize: 13 }
            RowLayout {
                Layout.fillWidth: true;spacing: 7
                Rectangle { width: 5;height: 5;radius: 3;color: hero.info.enabled===false ? Theme.secondary : hero.info.has_record ? Theme.accent : "#d9be82" }
                Label { Layout.fillWidth: true;elide: Text.ElideRight;font.pixelSize: 11;color: Theme.secondary;text: hero.info.enabled===false ? "监听已关闭" : hero.info.has_record ? "记录已连接 · 自动同步" : hero.info.has_schema ? "列表已缓存 · 等待成就记录" : "尚未匹配成就列表" }
            }
        }
        AchievementRing { Layout.preferredWidth: hero.width<620 ? 66 : 78;Layout.preferredHeight: width;completed: hero.info.unlocked || 0;total: hero.info.total || 0 }
    }
}
