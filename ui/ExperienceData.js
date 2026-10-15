.pragma library

function groupGames(games,mode) {
    var groups=[],lookup=Object.create(null)
    games.forEach(function(game) {
        var names=mode==="category" ? [game.category || "其他"] : mode==="series" ? [game.series || "未设系列"] : mode==="tags" ? (game.tags && game.tags.length ? game.tags : ["未设标签"]) : ["全部游戏"]
        names.forEach(function(name) {
            if(lookup[name]===undefined) { lookup[name]=groups.length;groups.push({name:name,items:[]}) }
            groups[lookup[name]].items.push(game)
        })
    })
    return groups
}

function atlas(games,mode) {
    var groups=groupGames(games,mode),assigned=Object.create(null),nodes=[],edges=[],labels=[]
    var buckets=groups.map(function(group) {
        var rows=group.items.filter(function(game) { if(assigned[game.id]) return false;assigned[game.id]=true;return true })
        return {name:group.name,items:rows}
    }).filter(function(group) { return group.items.length })
    var maxCount=Math.max.apply(null,[1].concat(buckets.map(function(g) { return g.items.length })))
    var radius=Math.max(180,Math.sqrt(maxCount)*65),cell=radius*2+160,columns=Math.max(1,Math.ceil(Math.sqrt(buckets.length)))
    var byId=Object.create(null)
    buckets.forEach(function(group,gi) {
        var cx=(gi%columns)*cell+cell/2,cy=Math.floor(gi/columns)*cell+cell/2
        labels.push({name:group.name,x:cx,y:cy-radius-50,count:group.items.length})
        group.items.forEach(function(game,i) {
            var angle=i*2.3999632297,r=i===0 ? 0 : 66*Math.sqrt(i)
            var node={game:game,x:cx+Math.cos(angle)*r,y:cy+Math.sin(angle)*r,group:group.name}
            byId[game.id]=node;nodes.push(node)
        })
    })
    // Edges mean shared metadata. Chain each real group rather than constructing
    // an O(n²) clique; every game remains one node even when it has several tags.
    if(mode!=="all") groups.forEach(function(group) {
        if(["其他","未设系列","未设标签"].indexOf(group.name)>=0) return
        for(var i=1;i<group.items.length;i++) edges.push({a:byId[group.items[i-1].id],b:byId[group.items[i].id],label:group.name})
    })
    return {nodes:nodes,edges:edges,labels:labels,width:Math.max(cell,columns*cell),height:Math.max(cell,Math.ceil(buckets.length/columns)*cell)}
}
