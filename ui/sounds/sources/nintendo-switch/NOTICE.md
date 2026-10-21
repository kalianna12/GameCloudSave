# Nintendo Switch 音效来源

用户指定素材库：https://github.com/TOM-BadEN/Nintendo-Switch-Sounds-Effect

固定来源提交：`70614a3e0b912068476ed54d9836d08e8d6878b0`，获取日期 2026-10-22。
本目录六个 WAV 原文件取自该提交的 `WAV/`，未执行仓库的提取程序。
`UPSTREAM_README.md` 原样保留上游说明（上游中文存在乱码，英文版权说明完整）。

**版权归 Nintendo Co., Ltd. 所有，不属于 CC0 素材。** 上游说明仅用于个人学习、研究及非商业参考；禁止用于商业项目、声称拥有版权或侵犯 Nintendo 的权利。仓库公开可下载不等于 Nintendo 授予再发行许可。本次按用户要求用于本地源码版，未打包或发布发行资产。

| 事件 | 上游 WAV |
| --- | --- |
| 移动 | SeGameIconFocus.wav |
| 确认 | SeBtnDecide.wav |
| 返回 | SeFooterDecideBack.wav |
| 打开 | SeDialogOpen.wav |
| 分组 | SeSelectFocus.wav |
| 布局切换 | SeDialogOpen_Accent.wav |

运行时使用 `../../library/classic-clear-*.wav`：保持原速，转为单声道 44.1kHz PCM16，裁剪及首尾淡入淡出，轻度低通和响度提升。逐文件来源、SHA256 与参数见 `../../library/manifest.json`。保持既有 `classic-clear` 配置编号，默认跟随布局时原版首页使用本组，其他布局保留各自音效。
