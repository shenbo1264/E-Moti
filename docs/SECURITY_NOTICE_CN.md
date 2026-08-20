# 安全提醒：公开发布前请先轮换密钥

本轮对 `E-Moti-submission.zip` 做发布前扫描时，检测到以下文件存在非空密钥字段：

```text
user_data/capability_settings.json
  screen_observation.vision_api_key

user_data/expression_settings.json
  api_key
```

本报告没有保存或展示密钥值。

请按以下顺序处理：

1. 在服务商后台撤销或轮换对应密钥；
2. 不要公开原课程提交包；
3. 使用 `public_config_template/` 中的空密钥配置重新构建；
4. 对最终 Release 再运行 `release_security.py`；
5. 检查 Git 历史、日志、截图和 ignored artifacts。

建议把旧密钥视为已经暴露，不要只从 ZIP 里删除后继续使用。
