"""Offline starting points for keyboard-only games; never replace a user's saved profile."""
from mapping_model import default_profile,validate,direction_keys,token_name,PAD_BUTTONS


# Each face/shoulder/menu/stick-click has an explicit binding and an honest action label.
# Alternative keys live on separate buttons, not in simultaneous confirmation chords.
_ARROWS={'DUp':(38,'菜单向上'),'DDown':(40,'菜单向下'),'DLeft':(37,'菜单向左'),'DRight':(39,'菜单向右')}
_TEMPLATES=(
    {'id':'vn','name':'01 · VN / Galgame 阅读型','summary':'双摇杆鼠标 · 确认、快进、历史与菜单',
     'note':'自动快捷键依游戏。若光标与选项来回跳动，请关闭游戏原生手柄或另一套映射；本方案不屏蔽实体手柄。',
     'left':('mouse','鼠标定位'),'right':('mouse','鼠标微调'),'leftSpeed':850,'rightSpeed':380,
     'buttons':dict(_ARROWS,A=(13,'确认 / 推进'),B=(27,'取消 / 返回'),X=(162,'按住快进'),Y=(32,'推进对话'),
          LB=('wheelup','历史 / 回看'),RB=(65,'自动（需支持 A 键）'),LT=('middle','隐藏文本（依游戏）'),RT=('left','鼠标确认'),
          LS=(9,'切换快进（依游戏）'),RS=(72,'隐藏文本（H，依游戏）'),Back=('right','存读档菜单'),Start=(27,'游戏菜单'))},
    {'id':'platform','name':'02 · 平台跳跃型','summary':'WASD 移动 · 跳跃、攻击、冲刺与互动',
     'note':'J / K / Q 是动作键起点，请与游戏内改键对应。重推不自动冲刺，避免走动时误触冲刺或抓取。',
     'left':('keys','移动'),'right':('mouse','菜单鼠标'),'rightSpeed':700,
     'buttons':dict(_ARROWS,A=(32,'跳跃'),B=(27,'取消 / 返回'),X=(74,'主攻击'),Y=(69,'互动'),
          LB=(81,'技能 / 道具'),RB=(75,'副攻击 / 技能'),LT=(162,'抓取 / 蹲下'),RT=(160,'冲刺'),
          LS=(160,'冲刺（按住）'),RS=('left','菜单点击'),Back=(9,'地图 / 信息'),Start=(27,'暂停菜单'))},
    {'id':'topdown','name':'03 · 俯视角动作型','summary':'八向移动 · 鼠标瞄准、攻击、翻滚与技能',
     'note':'Space / Q / F 用于翻滚和技能；不在重推时自动附加 Shift，避免影响瞄准和动作组合。',
     'left':('keys','移动'),'right':('mouse','瞄准'),'rightSpeed':1250,
     'buttons':{'A':(32,'翻滚 / 闪避'),'B':(69,'互动'),'X':(81,'技能一'),'Y':(70,'技能二'),
          'LB':(9,'武器 / 道具面板'),'RB':(82,'装填 / 特殊动作'),'LT':('right','次攻击 / 瞄准'),'RT':('left','主攻击'),
          'LS':(160,'冲刺（按住）'),'RS':('middle','锁定（依游戏）'),'Back':(77,'地图'),'Start':(27,'暂停菜单'),
          'DUp':(49,'快捷槽 1'),'DDown':(50,'快捷槽 2'),'DLeft':(51,'快捷槽 3'),'DRight':(52,'快捷槽 4')}},
    {'id':'shooter','name':'04 · FPS / TPS 键鼠模拟型','summary':'轻推走、重推跑 · 鼠标视角、瞄准与开火',
     'note':'需按游戏灵敏度调校右摇杆。这里输出的是鼠标，不能保证获得原生手柄的辅助瞄准。',
     'left':('keys','移动；重推 Shift 跑步'),'right':('mouse','视角'),'heavyShift':True,'rightSpeed':1600,'rightCurve':1.7,'rightSmoothing':12,
     'buttons':{'A':(32,'跳跃'),'B':(162,'蹲下（按住）'),'X':(82,'换弹'),'Y':(69,'互动'),
          'LB':(81,'技能 / 上一武器'),'RB':('wheeldown','切换武器'),'LT':('right','瞄准'),'RT':('left','开火'),
          'LS':(160,'跑步（按住）'),'RS':(86,'近战'),'Back':(9,'计分板 / 背包'),'Start':(27,'暂停菜单'),
          'DUp':(49,'主武器'),'DDown':(50,'副武器'),'DLeft':(71,'投掷物'),'DRight':(70,'照明 / 功能')}},
    {'id':'tactics','name':'05 · 回合制 / 战棋型','summary':'方向光标 · 确认、单位切换、翻页与鼠标',
     'note':'Space 暂定结束回合、Tab 切换单位；不同战棋游戏差别较大，请先核对这两项。',
     'left':('keys','方向光标'),'right':('mouse','鼠标选取'),'arrows':True,'rightSpeed':850,
     'buttons':dict(_ARROWS,A=(13,'确认目标'),B=(27,'取消'),X=(9,'切换单位 / 目标'),Y=(32,'结束回合（依游戏）'),
          LB=(33,'上一页 / 上一单位'),RB=(34,'下一页 / 下一单位'),LT=('right','取消鼠标选择'),RT=('left','选择目标'),
          LS=(162,'组合选择（按住）'),RS=('middle','拖动地图（依游戏）'),Back=(77,'地图'),Start=(27,'游戏菜单'))},
    {'id':'management','name':'06 · 模拟经营 / 城建型','summary':'鼠标工作台 · 滚轮缩放、暂停与视角移动',
     'note':'左摇杆定位，右摇杆上下缩放；中键按住拖动视角。WASD 相机和 Tab 面板请按游戏调整。',
     'left':('mouse','鼠标定位'),'right':('wheel','上下缩放'),'leftSpeed':1100,
     'buttons':{'A':(13,'确认'),'B':(27,'取消建造 / 返回'),'X':(32,'暂停 / 继续'),'Y':(9,'切换面板'),
          'LB':('wheelup','放大'),'RB':('wheeldown','缩小'),'LT':('right','右键取消'),'RT':('left','点击 / 按住拖放'),
          'LS':(160,'连续建造修饰键'),'RS':('middle','拖动视角（按住）'),'Back':(77,'地图'),'Start':(27,'游戏菜单'),
          'DUp':(87,'相机前移'),'DDown':(83,'相机后移'),'DLeft':(65,'相机左移'),'DRight':(68,'相机右移')}},
    {'id':'survival','name':'07 · 生存建造 / 沙盒型','summary':'移动与视角 · 互动、背包、制作与快捷栏',
     'note':'Tab 背包、C 制作、F 功能为常见起点；若游戏不同，可直接录入对应快捷键。',
     'left':('keys','移动；重推 Shift 跑步'),'right':('mouse','视角'),'heavyShift':True,'rightSpeed':1400,
     'buttons':{'A':(69,'互动 / 拾取'),'B':(32,'跳跃'),'X':(82,'换弹 / 工具动作'),'Y':(9,'背包'),
          'LB':('wheelup','上一快捷槽'),'RB':('wheeldown','下一快捷槽'),'LT':('right','次动作 / 瞄准'),'RT':('left','使用 / 攻击'),
          'LS':(160,'跑步（按住）'),'RS':(162,'蹲下（按住）'),'Back':(77,'地图'),'Start':(27,'游戏菜单'),
          'DUp':(49,'快捷槽 1'),'DDown':(50,'快捷槽 2'),'DLeft':(67,'制作（依游戏）'),'DRight':(70,'照明 / 功能')}},
    {'id':'rpgmaker','name':'08 · RPG Maker / 键盘 RPG','summary':'方向键移动 · Z 确定、X 取消、Shift 冲刺',
     'note':'按 RPG Maker 标准使用方向键；W 默认是下一页，不是上移。Z、Enter、Space 分配在不同按钮，存档从菜单操作。',
     'left':('keys','方向键移动；重推 Shift 冲刺'),'right':('mouse','鼠标辅助（依游戏）'),'arrows':True,'heavyShift':True,'rightSpeed':500,
     'buttons':dict(_ARROWS,A=(90,'确定'),B=(88,'取消'),X=(160,'冲刺（按住）'),Y=(27,'菜单'),
          LB=(33,'上一页 / 上一角色'),RB=(34,'下一页 / 下一角色'),LT=(32,'备选确定：Space'),RT=(13,'备选确定：Enter'),
          LS=(160,'冲刺（按住）'),RS=('right','鼠标取消（依游戏）'),Back=(27,'菜单 / 存档'),Start=(27,'游戏菜单'))},
)


def make_template(ident):
    spec=next((row for row in _TEMPLATES if row['id']==ident),None)
    if spec is None:raise ValueError('游戏模板不存在')
    profile=default_profile(spec['name']);profile['templateId']=ident
    if ident=='vn':profile['forward']['mouseMode']='absolute'
    profile['forward']['buttons']={button:[('K:'+str(key)) if isinstance(key,int) else 'M:'+key] for button,(key,_) in spec['buttons'].items()}
    for stick,field in (('LS','left'),('RS','right')):
        cfg=profile['forward']['sticks'][stick];cfg['mode']=spec[field][0]
        cfg['lightExtra']=[];cfg['hardExtra']=['K:160'] if field=='left' and spec.get('heavyShift') else []
        cfg['light']=direction_keys('arrows' if spec.get('arrows') else 'wasd');cfg['hard']=direction_keys('arrows' if spec.get('arrows') else 'wasd')
        cfg['speed']=spec.get(field+'Speed',cfg['speed']);cfg['curve']=spec.get(field+'Curve',cfg['curve']);cfg['smoothing']=spec.get(field+'Smoothing',cfg['smoothing'])
    return validate(profile)


def template_catalog():
    result=[]
    names={'LS':'左摇杆按下','RS':'右摇杆按下','DUp':'十字上','DDown':'十字下','DLeft':'十字左','DRight':'十字右'}
    for spec in _TEMPLATES:
        profile=make_template(spec['id']);buttons=profile['forward']['buttons']
        bindings=[{'input':names.get(button,button),'output':' + '.join(token_name(t) for t in buttons[button]),'action':spec['buttons'][button][1]} for button in PAD_BUTTONS]
        for stick,field,label in (('LS','left','左摇杆'),('RS','right','右摇杆')):
            mode=profile['forward']['sticks'][stick]['mode']
            output=('方向键' if spec.get('arrows') else 'WASD') if mode=='keys' else '鼠标移动' if mode=='mouse' else '鼠标滚轮'
            bindings.insert(0 if field=='left' else 1,{'input':label,'output':output,'action':spec[field][1]})
        result.append({key:spec[key] for key in ('id','name','summary','note')}|{'bindings':bindings})
    return result
