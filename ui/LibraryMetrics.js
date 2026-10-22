.pragma library

function tileWidth(section, size) {
    return section.kind === "store" ? Math.round(size * 1.65)
         : section.kind === "tiles" ? Math.round(size * 1.34)
         : section.kind === "recent" ? Math.round(size * .9) : size;
}

function sectionHeight(section, size) {
    return section.kind === "store" ? ((section.items || []).length ? 120 + size * .94 : 140)
         : section.kind === "tiles" ? 220 * size / 176
         : section.kind === "recent" ? 300 * size / 176 : 320 * size / 176;
}

function sectionLayout(sections, size, spacing) {
    var offsets = [], heights = [], y = 0;
    for (var i = 0; i < sections.length; i++) {
        var height = sectionHeight(sections[i], size);
        offsets.push(y); heights.push(height); y += height + spacing;
    }
    return {offsets: offsets, heights: heights, total: Math.max(0, y - spacing)};
}
