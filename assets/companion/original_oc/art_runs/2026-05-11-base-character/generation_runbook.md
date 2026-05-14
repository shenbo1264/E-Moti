# 下一次真实生图执行命令

## 当前阻塞

本轮只更新基准角色方向、prompt、manifest 和筛选文档，不声明任何图片已经生成。

当前环境不能直接完成真实 AI 生图：

- 本会话没有可调用的内置 `image_gen` 工具。
- 环境变量 `OPENAI_API_KEY` 未设置。

## 前置检查

在 `D:\学工文档\光核\电子宠物\E-Moti_demo` 下执行：

```powershell
if (-not $env:OPENAI_API_KEY) { throw "缺少 OPENAI_API_KEY，不能调用真实生图 API。" }
$env:IMAGE_GEN = "C:\Users\19970\.codex\skills\.system\imagegen\scripts\image_gen.py"
python $env:IMAGE_GEN generate --prompt "ping" --out "assets\companion\original_oc\art_runs\2026-05-11-base-character\outputs\ping.png" --dry-run
Remove-Item -LiteralPath "assets\companion\original_oc\art_runs\2026-05-11-base-character\outputs\ping.png" -ErrorAction SilentlyContinue
```

## 生成 6 张候选原图

每个候选先生成 2 张，不直接生成完整 atlas。

```powershell
$env:IMAGE_GEN = "C:\Users\19970\.codex\skills\.system\imagegen\scripts\image_gen.py"
$run = "assets\companion\original_oc\art_runs\2026-05-11-base-character"

python $env:IMAGE_GEN generate --prompt-file "$run\prompts\01_sweet_healing_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\sweet_healing_companion\raw\sweet_healing_companion_v01.png"
python $env:IMAGE_GEN generate --prompt-file "$run\prompts\01_sweet_healing_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\sweet_healing_companion\raw\sweet_healing_companion_v02.png"

python $env:IMAGE_GEN generate --prompt-file "$run\prompts\02_lively_bond_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\lively_bond_companion\raw\lively_bond_companion_v01.png"
python $env:IMAGE_GEN generate --prompt-file "$run\prompts\02_lively_bond_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\lively_bond_companion\raw\lively_bond_companion_v02.png"

python $env:IMAGE_GEN generate --prompt-file "$run\prompts\03_quiet_guardian_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\quiet_guardian_companion\raw\quiet_guardian_companion_v01.png"
python $env:IMAGE_GEN generate --prompt-file "$run\prompts\03_quiet_guardian_companion.prompt.txt" --size 1024x1024 --quality medium --output-format png --no-augment --out "$run\outputs\quiet_guardian_companion\raw\quiet_guardian_companion_v02.png"
```

## 生成 192x208 review 预览

原图生成后，用 ImageMagick 生成小尺寸检查图：

```powershell
$run = "assets\companion\original_oc\art_runs\2026-05-11-base-character"
$candidates = @("sweet_healing_companion", "lively_bond_companion", "quiet_guardian_companion")

foreach ($candidate in $candidates) {
  Get-ChildItem -LiteralPath "$run\outputs\$candidate\raw" -Filter "*.png" | ForEach-Object {
    $reviewName = $_.BaseName + "_192x208.png"
    magick $_.FullName -resize 192x208 -background none -gravity center -extent 192x208 "$run\outputs\$candidate\review\$reviewName"
  }
}
```

## 筛选记录要求

预览图生成后，按 `review_checklist.md` 做人工筛选：

- 先删除一票否决图。
- 每个候选只保留 1 张最佳图。
- 把最终待选图复制到 `outputs/shortlist/`。
- 在 `outputs/review_status.md` 里补充每个候选的总分、优点、风险和结论。

## 后续动作边界

选定唯一基准图后，只先试做 `idle`、`waving`、`review` 三行动画。`review` 可承载专注/学习状态，`waiting`/`Sleep` 可承载休息和低状态照顾；不要在基准图阶段生成完整 atlas。
