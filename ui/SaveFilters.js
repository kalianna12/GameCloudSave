.pragma library
function accept(row, mode, configured, query) {
    var candidates=row.candidates || [],state=row.status || ""
    var haystack=[row.name || "",row.english_name || "",(row.aliases || []).join(" "),row.applied_path || ""].join(" ").toLowerCase()
    if(query && haystack.indexOf(query.toLowerCase().trim())<0) return false
    if(mode===1) return !configured
    if(mode===2) return !configured && candidates.length===0 && ["running","saving","uploading"].indexOf(state)<0
    if(mode===3) return !configured && candidates.length>0
    if(mode===4) return configured
    if(mode===5) return state==="failed" || state==="local_only" && row.upload_requested
    return true
}
