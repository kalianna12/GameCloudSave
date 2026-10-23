import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

GridLayout {
    id: charts
    property var statistics: ({})
    property bool compact: false
    property bool perGame: false
    property bool cumulative: false
    columns: 3;columnSpacing: 10
    AchievementChart {
        objectName: "achievementCompletionChart";Layout.fillWidth: true;Layout.fillHeight: true
        title: charts.perGame ? "本游戏完成度" : "全部成就完成度";kind: "donut"
        values: [charts.statistics.unlocked || 0,charts.statistics.locked || 0];centerText: (charts.statistics.percent || 0)+"%"
        caption: (charts.statistics.unlocked || 0)+" 已解锁 / "+(charts.statistics.total || 0)+" 总数"
    }
    AchievementChart {
        objectName: "achievementBarChart";Layout.fillWidth: true;Layout.fillHeight: true
        title: charts.perGame ? "已解锁成就稀有度" : "游戏解锁数量";kind: "bar"
        values: charts.statistics.bar_values || [];labels: charts.statistics.bar_labels || []
        caption: charts.perGame ? "按来源提供的全球解锁率分组" : "解锁数量最多的 7 款游戏"
    }
    AchievementChart {
        objectName: "achievementTimelineChart";Layout.fillWidth: true;Layout.fillHeight: true
        title: charts.cumulative ? "期间累计解锁" : "期间解锁趋势";kind: "line"
        values: charts.cumulative ? charts.statistics.cumulative || [] : charts.statistics.daily || [];labels: charts.statistics.dates || []
        caption: (charts.statistics.dated_unlocks || 0)+" 项有日期的解锁"+((charts.statistics.bucket_days || 1)>1 ? " · 每 "+charts.statistics.bucket_days+" 天合计" : "")+((charts.statistics.unknown_dates || 0)>0 ? " · "+charts.statistics.unknown_dates+" 项时间未知" : "")
    }
}
