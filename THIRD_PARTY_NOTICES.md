# Third-party components

GameCloudSave project code is MIT-licensed. Third-party software and retrieved artwork remain under their own terms.

| Component | License / source |
|---|---|
| Python runtime and Tk/Tcl | [PSF and bundled third-party licenses](https://docs.python.org/3/license.html) |
| Qt / PySide6 / Shiboken6 | [Qt for Python license information](https://doc.qt.io/qtforpython-6/licenses.html); distributed as replaceable DLLs and modules, unmodified |
| rclone | [MIT and included dependency notices](https://rclone.org/licence/) |
| psutil | [BSD-3-Clause](https://github.com/giampaolo/psutil/blob/master/LICENSE) |
| Pillow (only when present in a build) | [HPND / included third-party licenses](https://github.com/python-pillow/Pillow/blob/main/LICENSE) |
| PyInstaller bootloader | [GPL with bootloader exception](https://pyinstaller.org/en/stable/license.html) |
| vgamepad and bundled ViGEm client | MIT: [vgamepad](https://github.com/yannbouteiller/vgamepad/blob/main/LICENSE), [ViGEmClient](https://github.com/nefarius/ViGEmClient/blob/master/LICENSE); the ViGEmBus system driver is optional and installed separately only on request |

The distribution includes licenses copied from the installed packages and rclone's license information in `licenses`. Game covers and platform names are not covered by the project MIT license. Steam Store, VNDB, Xbox and image search providers are optional metadata/artwork services. Image search results can be collected and displayed inside the application; store promotions open the official product page. Downloaded artwork remains subject to its owner's terms; the application does not redistribute a cover library. Navigation sounds are original project assets, not recordings taken from a game console.

Corresponding project source and build instructions are included in `source.zip`. The application dynamically loads its Qt/PySide libraries; replacement for debugging modified libraries is permitted. Upstream corresponding sources: [Qt 6.11 archives](https://download.qt.io/archive/qt/6.11/), [PySide 6.11 sources](https://download.qt.io/official_releases/QtForPython/pyside6/), [rclone source](https://github.com/rclone/rclone).
