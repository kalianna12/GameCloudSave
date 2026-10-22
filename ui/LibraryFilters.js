.pragma library
function matches(game,values) {
    var tags=values.tags || []
    return (!values.series || (game.series || "")===values.series)
        && (!tags.length || tags.some(function(tag) { return (game.tags || []).indexOf(tag)>=0 }))
        && (!values.year || (values.year==="unknown" ? !game.release_date : (game.release_date || "").slice(0,4)===values.year))
}
function options(games,retained) {
    var series=Object.create(null),tags=Object.create(null),years=Object.create(null)
    games.forEach(function(game) {
        if(game.series) series[game.series]=true
        ;(game.tags || []).forEach(function(tag) { tags[tag]=true })
        if(/^\d{4}-\d{2}-\d{2}$/.test(game.release_date || "")) years[game.release_date.slice(0,4)]=true
    })
    retained=retained || {}
    if(retained.series) series[retained.series]=true
    ;(retained.tags || []).forEach(function(tag) { tags[tag]=true })
    if(retained.year && retained.year!=="unknown") years[retained.year]=true
    return {series:Object.keys(series).sort(function(a,b) { return a.localeCompare(b) }),tags:Object.keys(tags).sort(function(a,b) { return a.localeCompare(b) }),years:Object.keys(years).sort().reverse()}
}
function count(values) { return (values.series ? 1 : 0)+(values.tags || []).length+(values.year ? 1 : 0) }
function describe(values) {
    return (values.series ? ["系列："+values.series] : []).concat((values.tags || []).length ? ["标签："+values.tags.join("、")] : []).concat(values.year ? ["年份："+(values.year==="unknown" ? "未记录" : values.year)] : []).join("\n")
}
