from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
import shutil
import tempfile

from PIL import Image, ImageDraw, ImageFont

from guanghe_companion.plugin_center_controller import PluginCenterController
from guanghe_companion.plugin_subsystem import PluginSubsystem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--png-output", type=Path)
    parser.add_argument("--plugin-root", type=Path, default=Path(__file__).resolve().parents[1] / "plugins")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="emoti-plugin-preview-") as tmp:
        fake_app = Path(tmp) / "app"
        fake_app.mkdir()
        shutil.copytree(args.plugin_root.resolve(), fake_app / "plugins")
        subsystem = PluginSubsystem(application_root=fake_app, user_data_root=Path(tmp) / "user")
        subsystem.start(); center = PluginCenterController(subsystem)
        # Demonstrate the optional interaction in the preview.
        center.set_enabled("emoti.bundled.stargazing", True)
        snapshot = center.snapshot()
        subsystem.shutdown()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(_html(snapshot), encoding="utf-8")
    if args.png_output:
        _png(snapshot, args.png_output)
    print(json.dumps({"ok": True, "output": str(args.output), "png_output": str(args.png_output or ""), "plugin_count": len(snapshot["plugins"])}, ensure_ascii=False, indent=2))
    return 0


def _html(snapshot: dict[str, object]) -> str:
    cards = []
    for row in snapshot.get("plugins", []):
        state = "已启用" if row.get("enabled") else "未启用"
        cards.append(f"<article><h2>{html.escape(str(row.get('name')))}</h2><p>{html.escape(str(row.get('description')))}</p><div><b>{state}</b> · 风险 {html.escape(str(row.get('risk_level')))}</div><pre>{html.escape(json.dumps(row.get('effective_settings', {}), ensure_ascii=False, indent=2))}</pre></article>")
    return """<!doctype html><meta charset='utf-8'><title>E-Moti 插件中心</title><style>body{font-family:system-ui,'Microsoft YaHei';max-width:1000px;margin:0 auto;padding:36px;background:#f4f7f8;color:#263238}header{background:white;padding:24px;border-radius:16px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:16px}article{background:white;border:1px solid #d6e1e7;border-radius:14px;padding:18px}pre{white-space:pre-wrap;background:#f7fbfd;padding:10px;border-radius:8px}</style>""" + f"<header><h1>{html.escape(str(snapshot['title']))}</h1><p>{html.escape(str(snapshot['subtitle']))}</p></header><main>{''.join(cards)}</main>"


def _font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def _png(snapshot: dict[str, object], path: Path) -> None:
    image = Image.new("RGB", (1440, 900), "#f4f7f8"); draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 45, 1385, 175), radius=24, fill="white", outline="#d6e1e7")
    draw.text((90, 72), str(snapshot["title"]), font=_font(42), fill="#1f343d")
    draw.text((90, 128), str(snapshot["subtitle"]), font=_font(22), fill="#536a75")
    y=220
    for row in snapshot.get("plugins", []):
        draw.rounded_rectangle((70,y,1370,y+175), radius=18, fill="white", outline="#d6e1e7")
        draw.text((100,y+24), str(row.get("name")), font=_font(30), fill="#1f5360")
        draw.text((100,y+72), str(row.get("description"))[:70], font=_font(20), fill="#445b66")
        state="已启用" if row.get("enabled") else "未启用"
        draw.text((100,y+122), f"{state}   风险：{row.get('risk_level','low')}   权限：{len(row.get('permissions',[]))}", font=_font(20), fill="#1f7a8c")
        y += 205
    path.parent.mkdir(parents=True, exist_ok=True); image.save(path, optimize=True)

if __name__ == "__main__": raise SystemExit(main())
