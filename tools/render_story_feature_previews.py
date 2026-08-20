from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def _font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def card(path: Path, title: str, lines: list[str]) -> None:
    image=Image.new("RGB",(1400,760),"#eef5f8"); draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((55,45,1345,715),radius=28,fill="white",outline="#cbdde5",width=3)
    draw.text((105,90),title,font=_font(42),fill="#1f343d")
    y=180
    for line in lines:
        draw.ellipse((110,y+8,126,y+24),fill="#5b9db4"); draw.text((150,y),line,font=_font(25),fill="#39525f"); y+=92
    path.parent.mkdir(parents=True,exist_ok=True); image.save(path,optimize=True)


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--output-dir',type=Path,required=True); args=parser.parse_args(argv)
    card(args.output_dir/'memory_album_preview.png','星屑回忆册',['第一次热牛奶被留下','重复投喂只进入近期日志','相关话题才会把回忆叫回来','玩家可以珍藏、纠正或忘记'])
    card(args.output_dir/'focus_companion_preview.png','探头时刻',['只读取前台程序粗分类和闲置时长','安静时段、冷却和拒绝记录共同决定时机','玩家确认后才启动本地动作','完成结果可以成为共同经历'])
    card(args.output_dir/'plugin_runtime_preview.png','E-Moti Plugin Runtime',['互动、记忆规则、表达 Provider 和页面都可扩展','每项注册都有插件所有者','停用插件会撤销动作与页面','已经发生的共同回忆仍然保留'])
    print('{"ok": true, "count": 3}')
    return 0
if __name__=='__main__': raise SystemExit(main())
