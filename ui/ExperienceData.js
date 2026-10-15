.pragma library

function groupGames(games,mode) {
    var groups=[],lookup=Object.create(null)
    games.forEach(function(game) {
        var names=mode==="year" ? [/^\d{4}-\d{2}-\d{2}$/.test(game.release_date || "") ? game.release_date.slice(0,4)+"年" : "日期未知"] : mode==="category" ? [game.category || "其他"] : mode==="series" ? [game.series || "未设系列"] : mode==="tags" ? (game.tags && game.tags.length ? game.tags : ["未设标签"]) : ["全部游戏"]
        names.forEach(function(name) {
            if(lookup[name]===undefined) { lookup[name]=groups.length;groups.push({name:name,items:[]}) }
            groups[lookup[name]].items.push(game)
        })
    })
    if(mode==="year") groups.sort(function(a,b) { return a.name==="日期未知" ? 1 : b.name==="日期未知" ? -1 : a.name.localeCompare(b.name) })
    return groups
}

function groupColor(name) {
    var colors=["#83cdbf","#e9c879","#b3a2ed","#e99eb8","#88b9ed","#e8aa7d","#9acb85","#d8b7a5","#91cbd4"],hash=0
    var category=["视觉小说","角色扮演","动作冒险","射击竞技","策略模拟","解谜休闲","竞速体育","音乐节奏","其他"].indexOf(name)
    if(category>=0) return colors[category]
    for(var i=0;i<name.length;i++) hash=(hash*31+name.charCodeAt(i))>>>0
    return colors[hash%colors.length]
}
function chronological(a,b,order) {
    var ad=a.release_date || "",bd=b.release_date || ""
    if(order!=="name") {
        if(!ad || !bd) { if(ad) return -1;if(bd) return 1 }
        else { var difference=ad.localeCompare(bd);if(difference) return order==="release_desc" ? -difference : difference }
    }
    return (a.name || a.id).localeCompare(b.name || b.id)
}
function atlas(games,mode,order) {
    order=order || "release_asc"
    var groups=groupGames(games,mode),assigned=Object.create(null),nodes=[],edges=[],labels=[]
    groups.forEach(function(g) { g.items.sort(function(a,b) { return chronological(a,b,order) }) })
    if(mode==="series" || mode==="year") groups.sort(function(a,b) { return chronological(a.items[0],b.items[0],order) || a.name.localeCompare(b.name) })
    // Prefer a specific shared tag over a broad genre when positioning a node.
    var tagOwner=Object.create(null)
    if(mode==="tags") groups.slice().sort(function(a,b) { return a.items.length-b.items.length || a.name.localeCompare(b.name) }).forEach(function(g) {
        g.items.forEach(function(game) { if(tagOwner[game.id]===undefined) tagOwner[game.id]=g.name })
    })
    var buckets=groups.map(function(group) {
        var rows=group.items.filter(function(game) { if(assigned[game.id] || mode==="tags" && tagOwner[game.id]!==group.name) return false;assigned[game.id]=true;return true })
        return {name:group.name,items:rows}
    }).filter(function(group) { return group.items.length })
    var totalArea=0
    buckets.forEach(function(g) { g.columns=Math.ceil(Math.sqrt(g.items.length)*1.15);g.width=g.columns*180+64;g.height=Math.ceil(g.items.length/g.columns)*216+96;totalArea+=g.width*g.height })
    var byId=Object.create(null),targetWidth=Math.max(960,Math.sqrt(totalArea)*1.3),x=24,y=24,rowHeight=0,worldWidth=0
    buckets.forEach(function(group,gi) {
        if(x>24 && x+group.width>targetWidth) { x=24;y+=rowHeight+48;rowHeight=0 }
        var color=groupColor(group.name)
        labels.push({name:group.name,x:x,y:y,width:group.width,height:group.height,count:group.items.length,color:color})
        group.items.forEach(function(game,i) {
            var row=Math.floor(i/group.columns),column=i%group.columns
            if(row%2) column=group.columns-1-column
            var node={game:game,x:x+96+column*180+(row%2 ? 24 : 0),y:y+152+row*216+(column%2 ? 18 : 0),group:group.name,color:color,width:144,height:174,ordinal:i+1}
            byId[game.id]=node;nodes.push(node)
        })
        worldWidth=Math.max(worldWidth,x+group.width);rowHeight=Math.max(rowHeight,group.height);x+=group.width+48
    })
    // Edges mean shared metadata. Chain each real group rather than constructing
    // an O(n²) clique; every game remains one node even when it has several tags.
    if(mode!=="all") groups.forEach(function(group) {
        if(["其他","未设系列","未设标签","日期未知"].indexOf(group.name)>=0) return
        for(var i=1;i<group.items.length;i++) edges.push({a:byId[group.items[i-1].id],b:byId[group.items[i].id],label:group.name,color:groupColor(group.name)})
    })
    return {nodes:nodes,edges:edges,labels:labels,width:Math.max(480,worldWidth+24),height:Math.max(360,y+rowHeight+24)}
}
