"""Validated, data-only bidirectional input profiles and frame-independent stick math."""
import copy
import math
import re

BUTTONS={'A':0x1000,'B':0x2000,'X':0x4000,'Y':0x8000,'LB':0x100,'RB':0x200,
         'Back':0x20,'Start':0x10,'LS':0x40,'RS':0x80,'DUp':1,'DDown':2,'DLeft':4,'DRight':8}
PAD_BUTTONS=[*BUTTONS,'LT','RT']
DIRECTIONS=['N','NE','E','SE','S','SW','W','NW']
PAD_OUTPUTS=PAD_BUTTONS+['LX+','LX-','LY+','LY-','RX+','RX-','RY+','RY-']
MOUSE=['left','right','middle','x1','x2','wheelup','wheeldown']
KEY_NAMES={8:'Backspace',9:'Tab',13:'Enter',16:'Shift',17:'Ctrl',18:'Alt',19:'Pause',20:'Caps Lock',27:'Esc',32:'Space',
           33:'Page Up',34:'Page Down',35:'End',36:'Home',37:'←',38:'↑',39:'→',40:'↓',44:'Print Screen',45:'Insert',46:'Delete',
           91:'Win 左',92:'Win 右',93:'菜单',106:'Num *',107:'Num +',109:'Num −',110:'Num .',111:'Num /',144:'Num Lock',145:'Scroll Lock',
           160:'Shift 左',161:'Shift 右',162:'Ctrl 左',163:'Ctrl 右',164:'Alt 左',165:'Alt 右',
           186:';',187:'=',188:',',189:'−',190:'.',191:'/',192:'`',219:'[',220:'\\',221:']',222:"'",226:'OEM 102'}
MODIFIERS={16,17,18,91,92,160,161,162,163,164,165}


def token_name(token):
    if token.startswith('P:'):return token[2:]
    if token.startswith('M:'):return {'left':'鼠标左键','right':'鼠标右键','middle':'鼠标中键','x1':'鼠标侧键 1','x2':'鼠标侧键 2','wheelup':'滚轮上','wheeldown':'滚轮下'}.get(token[2:],token)
    try:
        vk=int(token[2:])
        if 48<=vk<=90:return chr(vk)
        if 112<=vk<=135:return 'F'+str(vk-111)
        if 96<=vk<=105:return 'Num '+str(vk-96)
        return KEY_NAMES.get(vk,'VK '+str(vk))
    except (ValueError,TypeError):return str(token)


def chord(value, pad=False):
    if not isinstance(value,list) or len(value)>12:raise ValueError('组合最多包含 12 个按键')
    result=[]
    for token in value:
        if not isinstance(token,str):raise ValueError('按键格式无效')
        valid=(token.startswith('P:') and token[2:] in PAD_OUTPUTS) if pad else bool(re.fullmatch(r'K:(?:[1-9]\d{0,2})',token) and 1<=int(token[2:])<=254 or token.startswith('M:') and token[2:] in MOUSE)
        if not valid:raise ValueError('未知按键：'+token)
        if token not in result:result.append(token)
    return result


def number(value,low,high,label):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:raise ValueError(label+'超出范围')
    return value


def direction_keys(preset):
    """Complete eight-way preset; diagonals hold both cardinal keys."""
    up,right,down,left={'wasd':(87,68,83,65),'arrows':(38,39,40,37)}[preset]
    return {d:['K:'+str(v) for v in keys] for d,keys in zip(DIRECTIONS,
            ((up,),(up,right),(right,),(down,right),(down,),(down,left),(left,),(up,left)))}


def default_profile(name='默认配置'):
    stick=lambda mode:{'mode':mode,'deadzone':.18,'threshold':.72,'speed':1400,'curve':1.5,'smoothing':20,
                       'light':direction_keys('wasd'),'hard':direction_keys('wasd'),'lightExtra':[],'hardExtra':['K:160'],
                       'wheelLight':3,'wheelHard':12,'wheelInvert':False}
    return {'name':name,'mode':'pad_to_keys','padModel':'xbox','slot':-1,'forward':{'buttons':{'A':['K:32'],'B':['K:27'],'X':['K:69'],'Y':['K:82'],
            'LT':['M:right'],'RT':['M:left']},'sticks':{'LS':stick('keys'),'RS':stick('mouse')}},
            'reverse':{'routes':[{'id':'default-w','source':['K:87'],'targets':['P:LY+']},{'id':'default-s','source':['K:83'],'targets':['P:LY-']},
                       {'id':'default-a','source':['K:65'],'targets':['P:LX-']},{'id':'default-d','source':['K:68'],'targets':['P:LX+']},
                       {'id':'default-up','source':['K:38'],'targets':['P:LY+']},{'id':'default-down','source':['K:40'],'targets':['P:LY-']},
                       {'id':'default-left','source':['K:37'],'targets':['P:LX-']},{'id':'default-right','source':['K:39'],'targets':['P:LX+']},
                       {'id':'default-space','source':['K:32'],'targets':['P:A']}],
                       'strength':1.,'lightModifier':['K:160'],'lightStrength':.45,'ramp':60,'mouse':'RS','mouseSpeed':1200,'smoothing':25,'wheelPulse':100}}


def validate(profile):
    if not isinstance(profile,dict):raise ValueError('映射配置无效')
    result=copy.deepcopy(profile)
    result.setdefault('padModel','xbox')
    if result['padModel'] not in ('xbox','ps','joycon'):raise ValueError('手柄模型无效')
    if not isinstance(result.get('name'),str) or not 1<=len(result['name'].strip())<=40:raise ValueError('配置名须为 1 到 40 个字')
    if 'templateId' in result and not isinstance(result['templateId'],str):raise ValueError('模板标识无效')
    if result.get('mode') not in ('pad_to_keys','keys_to_pad'):raise ValueError('映射方向无效')
    if type(result.get('slot'))!=int or not -1<=result['slot']<=3:raise ValueError('手柄编号无效')
    forward=result.get('forward',{})
    if not isinstance(forward,dict) or not isinstance(forward.get('sticks'),dict):raise ValueError('摇杆配置无效')
    buttons=forward.get('buttons',{})
    if not isinstance(buttons,dict) or any(key not in PAD_BUTTONS for key in buttons):raise ValueError('手柄按键无效')
    forward['buttons']={key:chord(value) for key,value in buttons.items()}
    for key in ('LS','RS'):
        cfg=forward.get('sticks',{}).get(key,{})
        if not isinstance(cfg,dict):raise ValueError('摇杆配置无效')
        if cfg.get('mode') not in ('keys','mouse','wheel','disabled'):raise ValueError('摇杆模式无效')
        for field,value in (('wheelLight',3),('wheelHard',12),('wheelInvert',False)):cfg.setdefault(field,value)
        number(cfg['wheelLight'],1,30,'轻推滚动速度');number(cfg['wheelHard'],1,30,'重推滚动速度')
        if type(cfg['wheelInvert']) is not bool:raise ValueError('滚轮方向无效')
        number(cfg.get('deadzone'),.05,.6,'死区');number(cfg.get('threshold'),cfg['deadzone']+.08,.99,'重推阈值')
        number(cfg.get('speed'),100,5000,'鼠标速度');number(cfg.get('curve'),.5,3.5,'响应曲线');number(cfg.get('smoothing'),0,150,'平滑时间')
        for zone in ('light','hard'):
            if not isinstance(cfg.get(zone),dict) or set(cfg[zone])!=set(DIRECTIONS):raise ValueError('需要完整的八方向设置')
            cfg[zone]={direction:chord(value) for direction,value in cfg[zone].items()}
            cfg[zone+'Extra']=chord(cfg.get(zone+'Extra',[]))
    reverse=result.get('reverse',{})
    if not isinstance(reverse,dict):raise ValueError('反向映射配置无效')
    reverse.setdefault('wheelPulse',100);number(reverse['wheelPulse'],20,500,'滚轮保持时间')
    if not isinstance(reverse.get('routes'),list) or len(reverse['routes'])>160:raise ValueError('反向映射最多 160 条')
    ids=set()
    for route in reverse['routes']:
        if not isinstance(route,dict) or not isinstance(route.get('id'),str) or route['id'] in ids:raise ValueError('绑定编号无效')
        ids.add(route['id']);route['source']=chord(route.get('source',[]));route['targets']=chord(route.get('targets',[]),True)
    reverse['lightModifier']=chord(reverse.get('lightModifier',[]))
    for field,low,high in [('strength',.1,1),('lightStrength',.1,1),('ramp',0,500),('mouseSpeed',100,5000),('smoothing',0,150)]:number(reverse.get(field),low,high,field)
    if reverse.get('mouse') not in ('LS','RS','disabled'):raise ValueError('鼠标目标摇杆无效')
    return result


def pad_state(pad):
    return {'buttons':[key for key,mask in BUTTONS.items() if pad.buttons&mask]+(['LT'] if pad.left_trigger>=38 else [])+(['RT'] if pad.right_trigger>=38 else []),
            'LS':[max(-1,pad.lx/32767),max(-1,pad.ly/32767)],'RS':[max(-1,pad.rx/32767),max(-1,pad.ry/32767)]}


class Forward:
    def __init__(self):self.reset()
    def reset(self):self.active={};self.heavy={};self.sectors={};self.velocity={};self.residual=[0.,0.];self.wheel_phase={};self.wheel_steps=[]
    def frame(self,profile,state,dt):
        dt=max(0,min(.05,dt));desired=set();dx=dy=0.;self.wheel_steps=[]
        for button in state.get('buttons',[]):desired.update(profile['forward']['buttons'].get(button,[]))
        for key,cfg in profile['forward']['sticks'].items():
            x,y=state.get(key,[0.,0.]);magnitude=min(1.,math.hypot(x,y));was=self.active.get(key,False)
            active=magnitude>(cfg['deadzone']-.03 if was else cfg['deadzone']) and cfg['mode']!='disabled'
            self.active[key]=active
            if not active:
                self.heavy[key]=False;self.velocity[key]=[0.,0.];self.sectors.pop(key,None);self.wheel_phase.pop(key,None);continue
            heavy=magnitude>(cfg['threshold']-.025 if self.heavy.get(key) else cfg['threshold']+.025)
            self.heavy[key]=heavy
            if cfg['mode']=='wheel':
                sign=(1 if y>cfg['deadzone'] else -1 if y<-cfg['deadzone'] else 0)*(-1 if cfg.get('wheelInvert',False) else 1)
                previous,phase=self.wheel_phase.get(key,(0,0.))
                if not sign:self.wheel_phase.pop(key,None);continue
                # One immediate notch, then time-based repeats; switching direction clears the previous remainder.
                phase=(1. if sign!=previous else phase)+dt*cfg.get('wheelHard' if heavy else 'wheelLight',12 if heavy else 3)
                steps=min(3,int(phase));self.wheel_phase[key]=(sign,phase-steps)
                self.wheel_steps.extend(['wheelup' if sign>0 else 'wheeldown']*steps)
            elif cfg['mode']=='keys':
                angle=math.atan2(x,y)%(2*math.pi);previous=self.sectors.get(key)
                sector=int((angle+math.pi/8)/(math.pi/4))%8
                if previous is not None:
                    delta=abs((angle-previous*math.pi/4+math.pi)%(2*math.pi)-math.pi)
                    if delta<math.pi/8+.055:sector=previous
                self.sectors[key]=sector;zone='hard' if heavy else 'light'
                desired.update(cfg[zone][DIRECTIONS[sector]]);desired.update(cfg[zone+'Extra'])
            else:
                amount=max(0,(magnitude-cfg['deadzone'])/(1-cfg['deadzone']))**cfg['curve']
                length=max(.00001,math.hypot(x,y));target=[x/length*amount*cfg['speed'],-y/length*amount*cfg['speed']]
                alpha=1-math.exp(-dt/(cfg['smoothing']/1000)) if cfg['smoothing'] else 1
                old=self.velocity.get(key,[0.,0.]);current=[old[i]+alpha*(target[i]-old[i]) for i in range(2)];self.velocity[key]=current
                dx+=current[0]*dt;dy+=current[1]*dt
        self.residual[0]+=dx;self.residual[1]+=dy
        move=[int(value) for value in self.residual];self.residual=[self.residual[i]-move[i] for i in range(2)]
        if not any(self.active.get(key) and cfg['mode']=='mouse' for key,cfg in profile['forward']['sticks'].items()):self.residual=[0.,0.]
        return desired,move


class Reverse:
    def __init__(self):self.reset()
    def reset(self):self.axes={key:0. for key in ('LX','LY','RX','RY')}
    def frame(self,profile,held,mouse,dt):
        cfg=profile['reverse'];targets=set()
        for route in cfg['routes']:
            if route['source'] and set(route['source']).issubset(held):targets.update(token[2:] for token in route['targets'])
        light=bool(cfg['lightModifier']) and set(cfg['lightModifier']).issubset(held)
        strength=cfg['lightStrength'] if light else cfg['strength'];axes={}
        for key in self.axes:axes[key]=(int(key+'+' in targets)-int(key+'-' in targets))*strength
        for stick in ('L','R'):
            length=math.hypot(axes[stick+'X'],axes[stick+'Y'])
            if length>strength:
                axes[stick+'X']*=strength/length;axes[stick+'Y']*=strength/length
        mouse_stick=cfg['mouse'];dt=max(.001,min(.05,dt))
        if mouse_stick!='disabled':
            prefix=mouse_stick[0];axes[prefix+'X']=max(-1.,min(1.,axes[prefix+'X']+mouse[0]/(dt*cfg['mouseSpeed'])));axes[prefix+'Y']=max(-1.,min(1.,axes[prefix+'Y']-mouse[1]/(dt*cfg['mouseSpeed'])))
        for axis,target in axes.items():
            smoothing=cfg['smoothing'] if mouse_stick!='disabled' and axis[0]==mouse_stick[0] else cfg['ramp']
            alpha=1-math.exp(-dt/(smoothing/1000)) if smoothing else 1
            if target==0 and not (mouse_stick!='disabled' and axis[0]==mouse_stick[0]):self.axes[axis]=0.
            else:self.axes[axis]+=alpha*(target-self.axes[axis])
            if abs(self.axes[axis])<.001:self.axes[axis]=0.
        return {'buttons':sum(mask for key,mask in BUTTONS.items() if key in targets),'LT':255 if 'LT' in targets else 0,'RT':255 if 'RT' in targets else 0,
                **{axis:max(-32767,min(32767,round(value*32767))) for axis,value in self.axes.items()}}
