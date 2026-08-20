from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile

from PIL import Image, ImageDraw, ImageFont

from guanghe_companion.companion_story_runtime import CompanionStoryRuntime
from guanghe_companion.plugin_api import ActionRequest
from guanghe_companion.plugin_story_bridge import PluginStoryBridge
from guanghe_companion.plugin_subsystem import PluginSubsystem


def _font(size: int):
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def _sprite_frames(root: Path, motion: str = "Raised") -> list[Image.Image]:
    asset = root / "assets" / "companion" / "xingxi_pixel_pet"
    sheet = Image.open(asset / "spritesheet.png").convert("RGBA")
    manifest = json.loads((asset / "motion_manifest.json").read_text(encoding="utf-8"))
    row = manifest["motions"][motion]["row"]; count = manifest["motions"][motion]["frame_count"]
    w=manifest["frame_width"]; h=manifest["frame_height"]
    return [sheet.crop((i*w,row*h,(i+1)*w,(row+1)*h)) for i in range(count)]


def _scene(sprite: Image.Image, *, title: str, speech: str, footer: str, accent: str) -> Image.Image:
    image=Image.new("RGB",(1100,680),"#edf5f8"); draw=ImageDraw.Draw(image)
    draw.rounded_rectangle((45,35,1055,645),radius=28,fill="white",outline="#cbdde5",width=3)
    draw.text((85,70),title,font=_font(38),fill="#1f343d")
    panel=(650,155,1015,475); draw.rounded_rectangle(panel,radius=22,fill="#f7fbfd",outline=accent,width=3)
    scaled=sprite.resize((300,325),Image.Resampling.NEAREST); image.paste(scaled,(680,145),scaled)
    draw.rounded_rectangle((85,180,600,430),radius=20,fill="#f9fcfd",outline="#d6e1e7")
    # primitive wrap
    words=list(speech); lines=[]; line=""
    for ch in words:
        if len(line)>=18: lines.append(line); line=""
        line+=ch
    if line: lines.append(line)
    y=225
    for line in lines[:6]: draw.text((120,y),line,font=_font(27),fill="#39525f"); y+=44
    draw.text((90,555),footer,font=_font(23),fill="#1f7a8c")
    return image


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--gif-output',type=Path,required=True); parser.add_argument('--cover-output',type=Path,required=True); parser.add_argument('--report',type=Path,required=True); args=parser.parse_args(argv)
    root=Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='emoti-plugin-story-') as tmp:
        fake_app=Path(tmp)/'app'; fake_app.mkdir(); shutil.copytree((root/'plugins').resolve(), fake_app/'plugins')
        subsystem=PluginSubsystem(application_root=fake_app,user_data_root=Path(tmp)/'user'); subsystem.start()
        center_enabled=subsystem.host.set_enabled('emoti.bundled.stargazing',True); subsystem.host.reload_from_disk()
        story=CompanionStoryRuntime.create(user_data_root=Path(tmp)/'story',character_id='xingxi_pixel_pet')
        bridge=PluginStoryBridge(story,subsystem.runtime,'xingxi_pixel_pet')
        visible_before=any(a.action_id=='stargazing.watch' for a in subsystem.runtime.list_actions())
        first=bridge.execute_action(ActionRequest(action_id='stargazing.watch',character_id='xingxi_pixel_pet',now=100,state_snapshot={}))
        second=bridge.execute_action(ActionRequest(action_id='stargazing.watch',character_id='xingxi_pixel_pet',now=200,state_snapshot={}))
        memories=story.memory.store.load_memories()
        subsystem.host.set_enabled('emoti.bundled.stargazing',False); subsystem.host.reload_from_disk()
        visible_after=any(a.action_id=='stargazing.watch' for a in subsystem.runtime.list_actions())
        memory_after=story.memory.store.load_memories()
        subsystem.shutdown()
    sprites=_sprite_frames(root)
    scenes=[
        _scene(sprites[0],title='1  在插件中心启用「星图角落」',speech='插件增加了一项「一起看星星」互动。',footer='动作进入互动页；原有养成规则没有改变。',accent='#5b9db4'),
        _scene(sprites[1%len(sprites)],title='2  第一次一起看星星',speech=first.execution.speech,footer='第一次互动生成《第一次一起看星星》。',accent='#8269b2'),
        _scene(sprites[2%len(sprites)],title='3  再看一次',speech=second.execution.speech,footer='相处次数增加；长期回忆没有重复刷屏。',accent='#6b9b77'),
        _scene(sprites[3%len(sprites)],title='4  停用插件',speech='互动动作和插件页面已经撤销。',footer='共同经历仍留在回忆册里。',accent='#b98762'),
    ]
    args.gif_output.parent.mkdir(parents=True,exist_ok=True); scenes[0].save(args.gif_output,save_all=True,append_images=scenes[1:],duration=[1600]*4,loop=0,optimize=True)
    scenes[0].save(args.cover_output,optimize=True)
    report={
        'schema_version':1,'ok':visible_before and not visible_after and len(memories)==1 and len(memory_after)==1,
        'action_visible_after_enable':visible_before,'action_removed_after_disable':not visible_after,
        'first_speech':first.execution.speech,'first_memory_ids':list(first.memory_ids),'second_memory_ids':list(second.memory_ids),
        'first_memory_title':memories[0].title if memories else '', 'memory_count_after_second_action':len(memories),
        'memory_survives_disable':len(memory_after)==1,'gif':str(args.gif_output),'cover':str(args.cover_output)
    }
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n',encoding='ascii')
    print(json.dumps(report,ensure_ascii=False,indent=2)); return 0 if report['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
