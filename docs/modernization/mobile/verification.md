# 多端基础增量：实际验证记录

用户日期：2026-10-28（America/Los_Angeles）；执行时已是 2026-10-29 UTC。基线为上一批本地提交 `fa19b2cab14efe63b6b53a4894d76741a6b7c392`。测试时 HEAD 仍为该基线，工作树已经包含两个新增生产模块；不要把记录里的 HEAD 误读为“未修改基线通过了新测试”。最终交付提交由包内 `DELIVERY.json` 给出。

## 1. 结果

| 检查 | 实际结果 | 证明的范围 |
|---|---|---|
| 修改前相关测试 | 34 passed，0.39 秒 | 现有 prompt、persona、Plugin Story Bridge 与 controller contract 的前置样本 |
| 新增任务/观察测试 | 57 passed，0.39 秒 | 27 个任务契约、30 个观察生命周期用例 |
| 最终全量 pytest | **1390 passed, 1 failed**，stdout 107.17 秒 | 1391 总用例，0 errors、0 skipped |
| 未修改上一批基线的同一失败 | 1 failed，0.15 秒 | 同一环境下复现现有 Linux 视频 fixture 问题 |
| 本地 Personal Agent 演示 | **18/18 checks passed** | 实际 Python/SQLite/typed prompt，模拟手机与执行者输入 |

全量 JUnit 的 suite time 为 107.129 秒，与 pytest 最后打印的总耗时略有差异；记录分别保留，不把它们当作产品响应延迟。新模块没有调用模型、外部执行器或网络采集。

原始输出以无损 gzip 保存：

- [pytest-after.txt.gz](evidence/pytest-after.txt.gz)
- [pytest-after.xml.gz](evidence/pytest-after.xml.gz)
- [pytest-baseline-failure.txt.gz](evidence/pytest-baseline-failure.txt.gz)
- [verification.json](evidence/verification.json)：环境、hash、数量和未验证项。
- [personal-agent-smoke.json](evidence/personal-agent-smoke.json)：18 项检查及明确标识的模拟报告。

## 2. 环境与命令

隔离临时环境：Python 3.12.14、pytest 9.1.1、PySide6 6.11.0、Pillow 13.0.0、ddgs 9.16.1、edge-tts 7.3.1。依赖来自当前 `pyproject.toml`，未修改项目依赖声明。与上一批临时环境相比，Pillow 等开放版本范围解析到了更新版本；本轮基线失败复现与新代码全量测试使用同一新环境。

原临时 venv/native libraries 已回收，本轮重新建立。QtWebEngine 还需要 libXtst 和 libxkbfile；从 Ubuntu 官方源下载并解压到 `/tmp`，没有安装或更改系统包。执行既有 Live2D 测试时允许 loopback 监听，不启动项目远程服务。

```bash
python -m pytest tests/test_memory_prompt_lifecycle.py tests/test_plugin_story_bridge.py \
  tests/test_persona.py tests/test_plugin_enabled_controller_contract.py -q
python -m pytest tests/test_personal_tasks.py tests/test_device_context.py -q
python tools/run_personal_agent_smoke.py \
  --output docs/modernization/mobile/evidence/personal-agent-smoke.json
python -m pytest -q --disable-warnings \
  --junitxml=docs/modernization/mobile/evidence/pytest-after.xml
```

全量环境设置：`TZ=UTC`、`PYTHONPATH=<repo>/src`、`QT_QPA_PLATFORM=offscreen`、`QTWEBENGINE_DISABLE_SANDBOX=1`，以及临时 native-library 目录的 `LD_LIBRARY_PATH`。`PATH` 中优先使用隔离 venv，使原有子进程测试可使用相同 Python。WebEngine sandbox 开关只为本次隔离验收容器服务，未改产品启动设置。

复现失败的基线使用独立临时 worktree：

```bash
git worktree add --detach /tmp/emoti-multidevice-baseline fa19b2cab14efe63b6b53a4894d76741a6b7c392
# 在该目录，使用同一环境与其自己的 src：
python -m pytest \
  tests/test_portrait_video_source_pack_import.py::test_import_portrait_video_to_source_pack_cli_runs_from_repo_root -q
```

这次没有重复跑一套完整基线：本轮没有修改既有生产源码，上一批已有全量记录，本轮只针对当前唯一失败再次验证其来源。最终新工作树的完整套件已经运行。

## 3. 唯一全量失败

`test_import_portrait_video_to_source_pack_cli_runs_from_repo_root` 只创建 Windows 的 `ffmpeg.cmd` stub。Linux 上 `shutil.which("ffmpeg")` 找到系统 FFmpeg，对测试写入的假 MP4 报无法解码，因此 CLI 返回 1。该失败在 `fa19b2c` 同环境再次出现；也与上一批记录一致。

本批没有改测试期待、跳过该测试、替换系统 FFmpeg 或宣称 Windows 真机因此失败。与此次任务/观察模块无调用关系的既有问题，继续保留为明确未通过项。

## 4. 开发中实际发现的 bad case

### 4.1 可写角色身份会重新标记旧观察

初始实现把 `owner_id` / `character_id` 设为可写公开属性。宿主误将角色从 A 改成 B 后，已有 A 的观察内容被视图标成 B，`is_current()` 仍返回真。审查脚本复现后增加 `test_bound_identity_cannot_relabel_cached_observations`；修复前实际失败，修复后通过。

修复：绑定身份为只读 property；角色切换应关闭旧 buffer 后创建新实例。该修复防止宿主误用造成的串角色，不被描述为 Python 同进程代码的安全沙箱。

### 4.2 未被使用的观察过期，错误取消有效回复

初始 `_expire()` 删除任意旧行都会增加全局 revision。当前视图只引用两条仍有效的新观察时，无关旧行到期也使视图失效。新增 `test_expiry_of_unused_row_does_not_cancel_valid_snapshot` 后实际失败。

修复：普通过期只移除到期行；`is_current()` 对视图实际包含的行逐一检查存在性和完整内容。由授权/记忆版本改变引起的全局撤回仍生效。两个新增回归在修复前结果为 **2 failed, 28 passed**，修复后观察用例 **30 passed**。

### 4.3 网络未知结果不能视为未执行

任务测试覆盖发送权已提交后重开数据库、回执未知、第二个 store 再次领取。结果不再产生第二条可派发命令；状态要求核对。这里模拟的是丢回执/重启序列，没有向真实网络发送两次任务，也没有证明外部执行器恰好执行一次。

### 4.4 取消与完成发生竞态

先请求取消，再收到同一次外部执行的成功回执：保留成功结果、取消请求和 `completion_won_race`。其他终态之后的矛盾状态明确报错。测试证明 journal 的处理规则，不证明每种外部执行器都实现正确取消。

### 4.5 开源观察代码中的实际缺口

ActivityWatch Android 固定提交的 `WebWatcher.kt` 把 `incognito` 写死为 false 并带 TODO。该源码位置已由主代理再次直接读取；不能据此提供自动排除无痕浏览的承诺。研究与固定链接见 [Android 研究](android-research.md)。未运行该项目，因此没有宣称复现其设备行为。

## 5. 来源与兼容性检查

两个新模块仅用标准库，没有复制第三方实现或引入运行依赖。实际开源借鉴仍保留上一批 Graphiti RRF 许可；本轮其他项目用于设计/适配评估，不把整套 collector 或工作流平台加入主程序。

现有 `src` 受版本控制文件、角色资产、插件目录、打包脚本和 `pyproject.toml` 未改。两个模块没有被现有启动链自动导入/激活，所以没有新的默认网络、手机数据或存储迁移。新 task journal 仅在用户/宿主显式实例化时创建独立表；不能指向情感记忆数据库。

测试覆盖生产 Python 文件的指纹为：

```text
f3d427ce552672e18bfe56e8f592cd63c0ff3409c0a36b996f189c26851adf3c
```

算法：按路径排序 `src/**/*.py`，对每个文件依次累计相对 POSIX 路径、NUL、原始文件字节、NUL；共 105 个文件。交付时再次核对归档中的源码与此指纹一致。JSON 记录包含 stdout/XML 压缩前后 hash。

## 6. 没有验证的部分

没有 Android SDK/手机 APK 构建、HyperOS 4 真机、HarmonyOS HAP、macOS 最终包与 TCC、Windows 桌面/安装器、真实 Relay/Codex/Claude、网络配对与认证、持续 runner、推送、真实 LLM/OCR/VLM、采集耗电或模型响应延迟。没有执行 root、ADB、Shizuku、系统权限设置或设备操作。

新观察尚未进入桌面聊天历史/语音消费链，因此不能声称完整跨端遗忘或权限撤回已完成。`is_current()` 能拒绝过期视图；任何真正保存该视图派生结果的消费者，还必须实现来源失效、历史过滤和在途取消。已有记忆/人格测试继续通过不替代这个新的端到端门禁。
