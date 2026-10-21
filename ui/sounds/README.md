# 导航提示音

当前使用 `library/manifest.json` 中的 36 组事件、39 个预处理 WAV，素材来自公开的 CC0 音效库，来源与原文件位于 `sources/`。

- 默认首页：Kenney UI Audio / Interface Sounds 的轻触反馈，保留三种音色编号。
- 书柜：Kenney 的开书、翻书、放书、合书录音，以及 StarNinjas 的真实翻页录音。
- 影院：plopkot 的真实放映机录音，配合机械开关声。
- 星图：Kenney 的玻璃轻响和界面声，降调并添加短回响。

移动、确认、返回、打开、分组选择和布局切换分别取样。构建脚本 `scripts/build_navigation_library.py` 负责裁剪、滤波、淡入淡出、峰值与响度处理；开发时需要 soundfile/numpy，运行时仅使用预转换 PCM，无额外依赖或驱动。

`app/navigation_audio.py` 在后台线程预载；`app/native_audio.py` 使用 Windows 自带 XAudio2，将完整短音一次提交给原生混音线程。播放过程没有 Python 回调或补帧定时器，界面重建不会切断尾音。最多 8 个并发音轨，统一预留混音峰值空间；前台启用时维持原生静音循环，后台/关闭声音时停止。个性化中有四种布局的试听入口。

此目录顶层的 `navigation.wav`、旧的 12 个合成音和 `generate_navigation_sounds.py` 为历史资源，当前导航不使用。
