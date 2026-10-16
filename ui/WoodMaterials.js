.pragma library
var woods={
    oak:{base:"#977047",light:"#d8ad70",edge:"#e9c88c",dark:"#593d24",back:"#30241b",grain:"#51351e",title:"#f6e0b7"},
    walnut:{base:"#62412e",light:"#a2764c",edge:"#c29a68",dark:"#312218",back:"#211a16",grain:"#26180f",title:"#efd4ac"},
    cherry:{base:"#86503a",light:"#c18a61",edge:"#e2b381",dark:"#46271f",back:"#2a1c19",grain:"#4d281e",title:"#ffddbd"}
}
function material(name) { return woods[name] || woods.walnut }
