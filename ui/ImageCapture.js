(function () {
    // Read only the current search page. Never click links or solve challenges.
    var rows=[],seen=new Set();
    function decode(value) { try { return JSON.parse('"'+value+'"'); } catch(e) { return value.replace(/\\\//g,'/'); } }
    function add(image,thumb,name,page,w,h) {
        if(typeof image!=='string' || !/^https?:\/\//i.test(image) || seen.has(image) || rows.length>=64) return;
        w=Number(w)||0;h=Number(h)||0;if(w && h && (w<90 || h<90)) return;
        seen.add(image);rows.push({image:image,thumbnail:thumb||image,name:(name||document.title).slice(0,200),page:page||location.href,width:w,height:h});
    }
    document.querySelectorAll('[m]').forEach(function(el) {
        try { var m=JSON.parse(el.getAttribute('m'));if(m.murl) add(m.murl,m.turl,m.t||m.desc,m.purl,m.w,m.h); } catch(e) {}
    });
    document.querySelectorAll('a[href*="imgurl="],a[href*="mediaurl="]').forEach(function(a) {
        try { var u=new URL(a.href),img=a.querySelector('img');add(u.searchParams.get('imgurl')||u.searchParams.get('mediaurl'),img && (img.currentSrc||img.src),img && img.alt,u.searchParams.get('imgrefurl'),img && img.naturalWidth,img && img.naturalHeight); } catch(e) {}
    });
    var budget=6000000;
    Array.from(document.scripts).slice(0,100).forEach(function(script) {
        if(budget<=0 || rows.length>=64) return;
        var text=script.textContent.slice(0,Math.min(budget,1500000));budget-=text.length;
        var expression=/\["(https?:[^"\n]+)",\s*(\d{2,5}),\s*(\d{2,5})\]/g,match;
        while((match=expression.exec(text)) && rows.length<64) {
            var url=decode(match[1]);if(/encrypted-tbn|gstatic\.com|google\.com\//i.test(url)) continue;
            var google=/google\./.test(location.hostname);
            add(url,url,'',location.href,google ? match[3] : match[2],google ? match[2] : match[3]);
        }
    });
    document.querySelectorAll('img').forEach(function(img) {
        var source=img.getAttribute('data-ou')||img.getAttribute('data-iurl')||img.getAttribute('data-original')||img.getAttribute('data-src')||img.currentSrc||img.src;
        var w=img.naturalWidth||img.width,h=img.naturalHeight||img.height;
        if(w<90 || h<90) return;
        var a=img.closest('a');add(source,img.currentSrc||img.src,img.alt,a && a.href,w,h);
    });
    return JSON.stringify(rows);
})()
