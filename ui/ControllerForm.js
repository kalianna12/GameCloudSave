.pragma library

function available(items) { return items.filter(function(c) { return c && c.visible && c.enabled }) }
function reveal(control,scroll) {
    control.forceActiveFocus()
    var flick=scroll ? scroll.contentItem : null
    if(!flick || flick.contentY===undefined || !flick.contentItem) return
    var y=control.mapToItem(flick.contentItem,0,0).y,top=flick.contentY
    if(y<top) top=y-8
    else if(y+control.height>top+flick.height) top=y+control.height-flick.height+8
    flick.contentY=Math.max(flick.originY || 0,Math.min(Math.max(flick.originY || 0,flick.contentHeight-flick.height),top))
}
function indexOfFocus(items,item) {
    while(item) { var index=items.indexOf(item);if(index>=0) return index;item=item.parent }
    return -1
}
function activate(control) {
    if(control.popup) { control.popup.open();return }
    if(control.checkable===true && control.toggle) { control.toggle();if(control.toggled) control.toggled();if(control.clicked) control.clicked();return }
    if(control.clicked) control.clicked()
}
function handle(items,focus,command,scroll) {
    items=available(items);if(!items.length) return true
    var index=indexOfFocus(items,focus)
    if(index<0) { reveal(items[0],scroll);return true }
    var c=items[index]
    if(command==="up" || command==="down") { reveal(items[Math.max(0,Math.min(items.length-1,index+(command==="up" ? -1 : 1)))],scroll);return true }
    if(command==="activate") { activate(c);return true }
    if(command==="left" || command==="right") {
        var step=command==="left" ? -1 : 1
        if(c.count!==undefined && c.currentIndex!==undefined && c.activated) { c.currentIndex=Math.max(0,Math.min(c.count-1,c.currentIndex+step));c.activated(c.currentIndex) }
        else if(c.value!==undefined && c.from!==undefined) { c.value=Math.max(c.from,Math.min(c.to,c.value+step*(c.stepSize || 1)));if(c.moved) c.moved();else if(c.valueModified) c.valueModified() }
        else if(c.checkable===true && c.toggle) activate(c)
        else reveal(items[Math.max(0,Math.min(items.length-1,index+step))],scroll)
        return true
    }
    return true
}
