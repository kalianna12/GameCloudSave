"""Shared audio options and validation; no device or disk work on UI edits."""
PACKS=('auto','classic-clear','classic-soft','classic-arcade','shelf','cinema','atlas','felt','wood','water')
LAUNCHES=('auto','off','warm','projector','orbit')
DEFAULTS={'navigation_sounds':True,'navigation_volume':80,'navigation_sound_style':'clear','navigation_sound_pack':'auto','launch_sound':'auto'}

def validate(values):
    values=dict(values)
    # QML's Math.round is an integral JavaScript Number, delivered as a float.
    level=values.get('navigation_volume')
    if type(level)==float and level.is_integer():values['navigation_volume']=int(level)
    if set(values)-DEFAULTS.keys():raise ValueError('未知音效设置')
    if 'navigation_sounds' in values and type(values['navigation_sounds'])!=bool:raise ValueError('提示音开关无效')
    if 'navigation_volume' in values and (type(values['navigation_volume'])!=int or not 0<=values['navigation_volume']<=100):raise ValueError('提示音音量须为 0 到 100')
    for key,options in (('navigation_sound_pack',PACKS),('launch_sound',LAUNCHES),('navigation_sound_style',('clear','soft','arcade'))):
        if key in values and values[key] not in options:raise ValueError('音效选项无效')
    return dict(values)
