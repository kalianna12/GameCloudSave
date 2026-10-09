"""Versioned, data-only theme tokens. Imported themes cannot execute code."""
import re
PALETTES={
 'dark':{'name':'碳灰','dark':True,'background':'#181a1c','sidebar':'#202326','surface':'#282c30','hover':'#353b41','border':'#454d56','text':'#f3f5f7','secondary':'#a9b4bf','accent':'#80c942'},
 'light':{'name':'浅色','dark':False,'background':'#f1f3f5','sidebar':'#e5e9ee','surface':'#ffffff','hover':'#e6edf3','border':'#bac5cf','text':'#19232e','secondary':'#526474','accent':'#397cbd'},
 'midnight':{'name':'午夜蓝','dark':True,'background':'#121d2b','sidebar':'#18263a','surface':'#203248','hover':'#2e4662','border':'#425b78','text':'#edf5ff','secondary':'#a8c0dc','accent':'#72b7ec'},
 'violet':{'name':'深紫','dark':True,'background':'#201b29','sidebar':'#292333','surface':'#332c40','hover':'#443954','border':'#65577a','text':'#f5f0fc','secondary':'#beb1cf','accent':'#b59de3'}}
def luminance(value):
    rgb=[int(value[i:i+2],16)/255 for i in (1,3,5)]
    rgb=[channel/12.92 if channel<=.04045 else ((channel+.055)/1.055)**2.4 for channel in rgb]
    return sum(channel*weight for channel,weight in zip(rgb,(.2126,.7152,.0722)))
def validate(data):
    if not isinstance(data,dict) or data.get('schemaVersion')!=1:raise ValueError('主题必须使用 schemaVersion: 1')
    colors=data.get('colors',{})
    if not isinstance(colors,dict):raise ValueError('主题 colors 必须是对象')
    output={key:value for key,value in PALETTES['dark'].items()}
    for key in ('background','sidebar','surface','hover','border','text','secondary','accent'):
        value=colors.get(key,output[key])
        if not isinstance(value,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',value):raise ValueError('主题颜色需使用 #RRGGBB：'+key)
        output[key]=value
    bright=luminance(output['text']);base=luminance(output['background'])
    if (max(bright,base)+.05)/(min(bright,base)+.05)<4.5:raise ValueError('文字与背景对比度不足，请调整主题颜色')
    output['dark']=data.get('dark',True) is True
    output['name']=str(data.get('name','自定义'))[:40]
    return output
def resolve(settings):
    palette=dict(settings.get('custom_theme') or PALETTES['dark']) if settings.get('theme')=='custom' else dict(PALETTES.get(settings.get('theme','dark'),PALETTES['dark']))
    accent=settings.get('accent_color','')
    if re.fullmatch(r'#[0-9a-fA-F]{6}',accent or ''):palette['accent']=accent
    accent_light=luminance(palette['accent'])
    dark_contrast=(accent_light+.05)/(luminance('#10200a')+.05)
    light_contrast=1.05/(accent_light+.05)
    palette['onAccent']='#10200a' if dark_contrast>=light_contrast else '#ffffff'
    palette['motion']=settings.get('animations',True)
    return palette
