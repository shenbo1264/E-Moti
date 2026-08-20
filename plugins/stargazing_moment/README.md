# 星图角落（示例插件）

这个插件同时演示四种扩展点：

- 新增一个电子宠物互动：`一起看星星`；
- 首次完成后提出一条纪念回忆，由宿主校验并写入；
- 向 AI 表达上下文提供一个小型状态区；
- 向 PySide6 宿主提供一个通用页面 ViewModel 描述。

插件自身没有金币、背包、关系和存档的写权限。它只返回带类型的结果与提案，最终结算仍由 E-Moti 宿主完成。

验证：

```bash
python tools/validate_emoti_plugin.py plugins/stargazing_moment --activate
python tools/run_plugin_smoke.py
```
