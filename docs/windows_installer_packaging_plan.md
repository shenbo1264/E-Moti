# 星汐 Windows 安装包方案

核对日期：2026-05-22

## 目标

本方案的目标不是只生成一个裸 `exe`，而是生成一个可交付的 Windows 安装程序，例如：

```text
E-Moti_Setup_0.1.0.exe
```

用户双击安装后，应能通过桌面快捷方式或开始菜单快捷方式启动星汐 demo，不需要手动打开命令行，也不需要手动输入：

```powershell
python -m guanghe_companion.app
python -m guanghe_companion.app --pet-mode
```

## 已配置环境

当前机器已完成以下工具安装与核对：

- Python：`3.11.9`
- PySide6：`6.11.0`
- PyInstaller：`6.20.0`
- pyinstaller-hooks-contrib：`2026.5`
- Inno Setup：`6.7.2`
- Inno Setup 编译器：`C:\Users\19970\AppData\Local\Programs\Inno Setup 6\ISCC.exe`

当前项目工作区仍有运行产生的默认存档差异：

```text
M data/companion_save.json
```

该文件不应进入安装包方案提交，也不应作为打包脚本的输入状态依据。

## 工具链选择

推荐采用：

```text
PyInstaller onedir -> Inno Setup 安装器
```

不建议第一版直接做 PyInstaller `onefile`。原因是本项目使用 PySide6、Qt 插件和 `assets` 资源目录，`onefile` 会引入临时解压路径，资源定位和启动速度风险更高。`onedir` 先生成一个完整应用目录，再交给 Inno Setup 包成安装程序，评审交付更稳。

参考资料：

- PyInstaller GitHub：https://github.com/pyinstaller/pyinstaller
- PyInstaller 文档：https://pyinstaller.org/en/stable/
- Inno Setup GitHub：https://github.com/jrsoftware/issrc
- Inno Setup 命令行编译器文档：https://jrsoftware.org/ishelp/index.php?topic=compilercmdline
- PySide6 官方部署文档：https://doc.qt.io/qtforpython-6/deployment/index.html

## 推荐产物结构

第一版安装包建议输出：

```text
dist/
  E-Moti/
    E-Moti.exe
    assets/
    _internal/
    ...
  installer/
    E-Moti_Setup_0.1.0.exe
```

安装后建议目录：

```text
%LOCALAPPDATA%\Programs\E-Moti\
```

用户数据建议目录：

```text
%LOCALAPPDATA%\E-Moti\
```

这样可以避免安装到 `Program Files` 后因为权限问题无法写入存档。

## 后续实施内容

### 1. 冻结环境资源路径适配

当前资源路径依赖源码目录：

```python
Path(__file__).resolve().parents[2] / "assets"
```

打包后需要统一资源解析逻辑，至少覆盖：

- 源码运行
- PyInstaller `onedir`
- 后续可能的 PyInstaller `onefile`

资源目录必须能找到：

- `assets/companion/original_oc/character.json`
- `assets/companion/original_oc/motion_manifest.json`
- `assets/companion/original_oc/spritesheet.png`
- `assets/companion/original_oc/shop_items.json`
- `assets/companion/original_oc/item_icons/*`

### 2. 用户数据路径适配

安装包运行时不应默认写入仓库内：

```text
data/companion_save.json
```

建议新增运行时数据目录解析：

```text
%LOCALAPPDATA%\E-Moti\companion_save.json
%LOCALAPPDATA%\E-Moti\companion_demo_save.json
```

源码开发模式可继续使用当前仓库内 `data/`，但安装包模式应使用用户目录。

### 3. 应用启动入口

建议增加明确入口文件，避免安装器直接依赖 `python -m`：

```text
packaging/launch_control_panel.py
packaging/launch_pet_mode.py
```

两个入口分别等价于：

```powershell
python -m guanghe_companion.app --demo-save
python -m guanghe_companion.app --pet-mode --demo-save
```

是否默认使用 `--reset-demo-save` 需要谨慎。安装后的普通启动不应每次重置；评审演示可以单独提供“重置演示状态”的快捷方式或命令。

### 4. PyInstaller 构建脚本

建议新增：

```text
tools/build_windows_app.ps1
```

职责：

- 清理上一轮 `build/` 和 `dist/E-Moti/`
- 调用 PyInstaller
- 使用 `--onedir`
- 使用 `--windowed`
- 包含 `assets`
- 包含必要 Qt/PySide6 运行依赖
- 输出 `dist/E-Moti/E-Moti.exe`

### 5. Inno Setup 安装器脚本

建议新增：

```text
packaging/e-moti-installer.iss
tools/build_windows_installer.ps1
```

安装器职责：

- 将 `dist/E-Moti/` 安装到目标目录
- 创建桌面快捷方式
- 创建开始菜单快捷方式
- 提供卸载入口
- 安装包输出到 `dist/installer/`

第一版快捷方式建议：

- `星汐 E-Moti`
- `星汐桌宠模式`

如需演示排练，可再加：

- `星汐演示重置`

### 6. 图标策略

第一版可以先使用默认图标，避免引入新的美术资源流程。若要替换图标，应单独走候选、可见 QA、正式替换、重新验证、人工 QA，不在本安装包小切片里混入正式美术替换。

## 测试与验收

后续实现时应先写测试，再写实现。建议验收命令：

```powershell
python -m pytest
python -m json.tool assets\companion\original_oc\shop_items.json
powershell -ExecutionPolicy Bypass -File tools\build_windows_app.ps1
powershell -ExecutionPolicy Bypass -File tools\build_windows_installer.ps1
```

安装器验收：

1. 双击 `E-Moti_Setup_0.1.0.exe` 可以安装。
2. 桌面快捷方式可以打开控制面板模式。
3. 桌宠模式快捷方式可以打开 sprite-only 桌宠窗口。
4. 关闭程序后不会污染仓库内 `data/companion_save.json`。
5. 卸载入口可用。
6. 安装后无 Python 环境也应可运行。

如果后续改动 UI 或桌宠启动入口，需要重新跑 PySide 可视 smoke。

## 风险

- PyInstaller `onefile` 可能启动慢，且资源路径更容易出问题；第一版不作为主路线。
- Qt 平台插件缺失会导致 exe 启动失败，需要通过打包 smoke 尽早暴露。
- 安装到 `Program Files` 时存档写入可能失败，因此安装版应使用 `%LOCALAPPDATA%\E-Moti`。
- 不应把 LLM、TTS、联网搜索、MotionLayer 或美术替换混入安装包小切片。
- 不应声称“轻触 / 共同学习发色偏白”已解决；这仍是已知搁置风险。

## 推荐下一步

下一包建议命名为：

```text
Windows 安装器最小交付包
```

实施顺序：

1. 写资源路径和用户数据路径测试。
2. 实现冻结环境路径 helper。
3. 新增两个打包入口。
4. 新增 PyInstaller 构建脚本。
5. 新增 Inno Setup 脚本和安装器构建脚本。
6. 构建安装器并做安装后启动验证。
7. 跑全量测试并提交。

