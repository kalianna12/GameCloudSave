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
function constellation(count,seed) {
    // Small groups read as recognisable silhouettes; larger collections grow
    // around them on a golden-angle spiral. Stable positions never wander.
    var shapes=[
        [[0,0],[1,-.4],[1.8,.4],[1.1,1.2],[.2,1.7],[-.7,1.1],[-1,.2]],
        [[0,0],[-1,-.5],[-1.8,.1],[-2.3,1],[.8,.6],[1.6,.2],[2.1,-.7]],
        [[0,0],[.8,-.7],[1.7,-.1],[1.5,1],[.4,1.5],[-.5,.8],[-1.5,1.1]],
        [[0,0],[-.8,.6],[-.4,1.5],[.6,2.1],[1.7,2],[2.2,1.1],[1.6,.3]],
        [[0,0],[1.1,.1],[1.6,1],[.7,1.8],[-.5,1.5],[-1.2,.5],[-1.8,-.4]]
    ],shape=shapes[seed%shapes.length],points=[],cells=Object.create(null),angle=(seed%9-4)*.11
    function near(x,y) {
        var cx=Math.floor(x/180),cy=Math.floor(y/210)
        for(var dx=-1;dx<=1;dx++) for(var dy=-1;dy<=1;dy++) {
            var bucket=cells[(cx+dx)+":"+(cy+dy)] || []
            for(var k=0;k<bucket.length;k++) if(Math.abs(x-bucket[k].x)<172 && Math.abs(y-bucket[k].y)<206) return true
        }
        return false
    }
    for(var i=0;i<count;i++) {
        var raw=i<shape.length ? shape[i] : [Math.cos(i*2.39996)*Math.sqrt(i)*.72,Math.sin(i*2.39996)*Math.sqrt(i)*.72]
        var px=(raw[0]*Math.cos(angle)-raw[1]*Math.sin(angle))*210,py=(raw[0]*Math.sin(angle)+raw[1]*Math.cos(angle))*230
        var tries=0
        while(near(px,py)) {
            var theta=i*2.39996+tries*.43,radius=150*Math.sqrt(i+1)+tries*24
            px=Math.cos(theta)*radius;py=Math.sin(theta)*radius;tries++
        }
        var point={x:px,y:py};points.push(point)
        var key=Math.floor(px/180)+":"+Math.floor(py/210);if(!cells[key]) cells[key]=[];cells[key].push(point)
    }
    var minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity
    points.forEach(function(p) { minX=Math.min(minX,p.x);minY=Math.min(minY,p.y);maxX=Math.max(maxX,p.x);maxY=Math.max(maxY,p.y) })
    points.forEach(function(p) { p.x+=100-minX;p.y+=160-minY })
    return {points:points,width:maxX-minX+200,height:maxY-minY+280}
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
    buckets.forEach(function(g,gi) { var seed=gi;for(var j=0;j<g.name.length;j++) seed=(seed*31+g.name.charCodeAt(j))>>>0;g.shape=constellation(g.items.length,seed);g.width=g.shape.width;g.height=g.shape.height })
    var byId=Object.create(null),placed=[],minX=0,minY=0,maxX=0,maxY=0
    buckets.forEach(function(group,gi) {
        var x=0,y=0,attempt=0
        function clashes() { return placed.some(function(p) { return x<p.x+p.width+90 && x+group.width+90>p.x && y<p.y+p.height+90 && y+group.height+90>p.y }) }
        while(gi && clashes()) {
            var radius=220*Math.sqrt(++attempt),theta=attempt*2.39996
            x=Math.cos(theta)*radius-group.width/2;y=Math.sin(theta)*radius-group.height/2
        }
        placed.push({x:x,y:y,width:group.width,height:group.height})
        minX=Math.min(minX,x);minY=Math.min(minY,y);maxX=Math.max(maxX,x+group.width);maxY=Math.max(maxY,y+group.height)
        var color=groupColor(group.name)
        labels.push({name:group.name,x:x,y:y,width:group.width,height:group.height,count:group.items.length,color:color})
        group.items.forEach(function(game,i) {
            var point=group.shape.points[i]
            var node={game:game,x:x+point.x,y:y+point.y,group:group.name,color:color,width:144,height:174,ordinal:i+1}
            byId[game.id]=node;nodes.push(node)
        })
    })
    nodes.forEach(function(n) { n.x+=24-minX;n.y+=24-minY })
    labels.forEach(function(g) { g.x+=24-minX;g.y+=24-minY })
    // Edges mean shared metadata. Chain each real group rather than constructing
    // an O(n²) clique; every game remains one node even when it has several tags.
    if(mode!=="all") groups.forEach(function(group) {
        if(["其他","未设系列","未设标签","日期未知"].indexOf(group.name)>=0) return
        for(var i=1;i<group.items.length;i++) {
            var node=byId[group.items[i].id],previous=byId[group.items[i-1].id]
            if(mode==='category' || mode==='tags') {
                var cost=Infinity
                for(var j=Math.max(0,i-32);j<i;j++) {
                    var candidate=byId[group.items[j].id],distance=Math.hypot(candidate.x-node.x,candidate.y-node.y)
                    if(distance<cost) { cost=distance;previous=candidate }
                }
            }
            edges.push({a:previous,b:node,label:group.name,color:groupColor(group.name)})
        }
    })
    return {nodes:nodes,edges:edges,labels:labels,width:Math.max(480,maxX-minX+48),height:Math.max(360,maxY-minY+48)}
}
