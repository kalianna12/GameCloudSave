.pragma library

function known(row) { return row.rarity_known || row.rarity>0 }
function rarity(row) {
    if(!known(row)) return "稀有度未知"
    return row.rarity<=1 ? "极稀有" : row.rarity<=10 ? "稀有" : row.rarity<=50 ? "不常见" : "常见"
}
function color(row,fallback,dark) {
    if(!known(row)) return fallback
    return row.rarity<=1 ? (dark===false ? "#765698" : "#b7a4d9") : row.rarity<=10 ? (dark===false ? "#286c82" : "#78bfd4") : fallback
}
function title(row,reveal) { return reveal ? row.secret_name || row.name : row.name }
function description(row,reveal) { return reveal ? row.secret_description || row.description : row.description }
