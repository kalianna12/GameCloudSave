import QtQuick

ListModel {
    id: records
    dynamicRoles: true
    property var signatures: ({})
    function findId(ident) {
        for(var i=0;i<count;i++) if(get(i).record.id===ident) return i
        return -1
    }
    function updateRecords(rows) {
        var wanted=Object.create(null),next=Object.create(null),structural=false
        for(var i=0;i<rows.length;i++) wanted[rows[i].id]=true
        for(var old=count-1;old>=0;old--) if(!wanted[get(old).record.id]) { remove(old);structural=true }
        for(var position=0;position<rows.length;position++) {
            var row=rows[position],at=position<count && get(position).record.id===row.id ? position : findId(row.id),signature=JSON.stringify(row)
            if(at<0) { insert(position,{record:row});structural=true }
            else {
                if(at!==position) { move(at,position,1);structural=true }
                if(signatures[row.id]!==signature) setProperty(position,"record",row)
            }
            next[row.id]=signature
        }
        signatures=next
        return structural
    }
}
