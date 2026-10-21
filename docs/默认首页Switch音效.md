# 默认首页 Switch 音效

2026-10-22，按用户指定的 [素材库](https://github.com/TOM-BadEN/Nintendo-Switch-Sounds-Effect)，固定提交 `70614a3e0b912068476ed54d9836d08e8d6878b0`。只下载六个使用的 WAV 原文件和 README，不运行其提取工具。

默认原版首页的 `classic-clear` 音效替换为 Switch，个性化列表显示“Switch · 默认”。保留已有配置编号；默认 `auto` 在原版首页使用该声音，书柜、影院、星图继续跟随各自布局。也可以单独选 Switch 用于所有布局。显式选其他声音的用户保持自己的选择，不重写真实设置。游戏启动声音保持现有独立选择。

| 事件 | 来源 | 实际 RMS | 对比旧默认响度 |
| --- | --- | --- | --- |
| 移动 | SeGameIconFocus.wav | 0.0641 | +4.1dB |
| 确认 | SeBtnDecide.wav | 0.0642 | +2.3dB |
| 返回 | SeFooterDecideBack.wav | 0.0641 | +3.3dB |
| 打开 | SeDialogOpen.wav | 0.0892 | +4.2dB |
| 分组 | SeSelectFocus.wav | 0.0455 | +1.3dB |
| 布局切换 | SeDialogOpen_Accent.wav | 0.0726 | +2.4dB |

保持原速，单声道 44.1kHz PCM16，首尾淡入淡出、8kHz 低通、目标 RMS 0.080/0.095，受峰值 0.28 上限约束。沿用八轨、主增益 0.44 的原生 XAudio2 混音及静音保活，最坏同相八轨叠加仍小于满幅。没有提高其他音效组的响度、改变用户音量或增加运行依赖。其他 54 个成品 WAV 与上一提交相同。

来源清单从全局 CC0 改为逐项许可：六个 Switch 声音标记 Nintendo-copyright，其余标记 CC0-1.0。Switch 素材版权归 Nintendo，上游说明用途为个人学习、研究及非商业参考；不把仓库公开下载视为 Nintendo 授权再发行。原文件 SHA256、处理参数和版权说明保存在源码目录。此轮没有构建或上传任何发行包。

验证均使用隔离数据，设备输出静音：

- `tests/test_navigation_audio.py`：8 项通过，含来源 SHA256、响度提高、淡入淡出、八轨最坏叠加峰值、原生音轨生命周期和静音。
- `tests/test_audio_settings.py`：3 项通过，含即时主音量及旧配置保留。
- `tests/test_navigation_audio_output.py`：57 事件组预载；四布局连续导航；Switch 布局切换音在 GUI 线程 `time.sleep(.35)` 阻塞期间原生采样继续推进，underruns 不增加；空闲、焦点和开关行为正常。
- `tests/test_audio_settings_ui.py`：实际 QML 个性化页的九组选择、手柄下拉和音量、即时保存且无整页刷新、启动试听与取消通过。

真实 `data`287个文件与既有 SHA256 基线一致。`source-preview` 为用户正在使用的库，游戏、配置和存档未更改；仅已有运行程序的推荐缓存和日志与早前基线不同，未清理或覆盖。

验证可客观排除成品削波和测试条件下的音频断流；主观听感、用户实际设备的空闲唤醒杂音仍需重启源码版试听确认。便携版和安装版未更新。
