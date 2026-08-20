# Windows 一键合入与验收

```powershell
python tools\apply_and_verify_emoti_overlay.py <E-Moti仓库路径> `
  --submission-zip <E-Moti-submission.zip> `
  --run-private-api-smoke `
  --run-windows-build `
  --run-installer-build `
  --report artifacts\plugin-overlay-verification\final_report.json
```

先在本地分支执行，禁止 Push。若上游 `app.py` 或构建脚本 SHA 已变化，停止自动覆盖，人工复核差异；不要直接使用 `--force` 掩盖真实冲突。
