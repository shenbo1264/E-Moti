from __future__ import annotations

"""Low-cost private provider smoke with redacted output.

Keys are read from a private submission ZIP in memory. They are never printed or
written to the report. Network failure is reported; use --require-online to make
it fatal.
"""

import argparse
import json
import queue
import threading
from pathlib import Path
import time
import urllib.error
import urllib.request
import zipfile


def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, object]:
    return json.loads(archive.read(name).decode('utf-8-sig'))


def _post(url: str, api_key: str, payload: dict[str, object], *, mimo: bool=False, timeout: float=5.0) -> tuple[int,float,dict[str,object]]:
    data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
    headers={'Content-Type':'application/json', ('api-key' if mimo else 'Authorization'): (api_key if mimo else f'Bearer {api_key}')}
    req=urllib.request.Request(url,data=data,headers=headers,method='POST'); started=time.perf_counter()
    try:
        with urllib.request.urlopen(req,timeout=timeout) as response:
            raw=response.read(65536); status=int(response.status)
        decoded=json.loads(raw.decode('utf-8')) if raw else {}
        return status,time.perf_counter()-started,decoded if isinstance(decoded,dict) else {}
    except urllib.error.HTTPError as exc:
        return int(exc.code),time.perf_counter()-started,{}




def _bounded_post(
    url: str,
    api_key: str,
    payload: dict[str, object],
    *,
    mimo: bool = False,
    timeout: float = 5.0,
) -> tuple[int, float, dict[str, object]]:
    """Run one provider request with a hard caller-visible deadline.

    Some DNS stacks can outlive urllib's socket timeout. The request runs in a
    daemon thread so the smoke command can return on schedule without waiting
    for a blocked resolver. The thread never prints or persists the key.
    """

    results: queue.Queue[tuple[str, object]] = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            results.put(("ok", _post(url, api_key, payload, mimo=mimo, timeout=timeout)))
        except Exception as exc:
            results.put(("error", type(exc).__name__))

    thread = threading.Thread(target=worker, name="emoti-provider-smoke", daemon=True)
    thread.start()
    thread.join(timeout + 2.0)
    if thread.is_alive():
        raise TimeoutError("provider request exceeded the smoke-test deadline")
    try:
        kind, value = results.get_nowait()
    except queue.Empty as exc:
        raise RuntimeError("provider worker exited without a result") from exc
    if kind == "error":
        raise RuntimeError(str(value))
    return value  # type: ignore[return-value]


def main(argv=None):
    parser=argparse.ArgumentParser(); parser.add_argument('--submission-zip',type=Path,required=True); parser.add_argument('--report',type=Path,required=True); parser.add_argument('--require-online',action='store_true'); parser.add_argument('--timeout',type=float,default=5.0); args=parser.parse_args(argv)
    with zipfile.ZipFile(args.submission_zip) as archive:
        expression=_read_json(archive,'user_data/expression_settings.json'); capability=_read_json(archive,'user_data/capability_settings.json')
    tests=[]
    expr_key=str(expression.get('api_key','')); expr_base=str(expression.get('base_url','')).rstrip('/'); expr_model=str(expression.get('model',''))
    if expr_key and expr_base and expr_model:
        url=expr_base if expr_base.endswith('/chat/completions') else expr_base+'/chat/completions'
        payload={'model':expr_model,'messages':[{'role':'user','content':'请只回复两个字：可用'}],'max_tokens':128,'temperature':0}
        try:
            status,latency,response=_bounded_post(url,expr_key,payload,timeout=max(1.0,float(args.timeout)))
            content=((response.get('choices') or [{}])[0].get('message') or {}).get('content','') if response else ''
            row={'provider':str(expression.get('provider','')),'model':expr_model,'http_status':status,'latency_ms':round(latency*1000),'response_present':bool(content),'network_reachable':True}
            if not 200 <= status < 300:
                row['error_type']='HTTPError'
            tests.append(row)
        except Exception as exc:
            tests.append({'provider':str(expression.get('provider','')),'model':expr_model,'http_status':0,'latency_ms':0,'response_present':False,'network_reachable':False,'error_type':type(exc).__name__})
    screen=capability.get('screen_observation',{}) if isinstance(capability,dict) else {}
    vision_key=str(screen.get('vision_api_key','')) if isinstance(screen,dict) else ''
    vision_base=str(screen.get('vision_base_url','')).rstrip('/') if isinstance(screen,dict) else ''
    vision_model=str(screen.get('vision_model','')) if isinstance(screen,dict) else ''
    if vision_key and vision_base and vision_model:
        url=vision_base if vision_base.endswith('/chat/completions') else vision_base+'/chat/completions'
        tiny='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n2sAAAAASUVORK5CYII='
        payload={'model':vision_model,'messages':[{'role':'user','content':[{'type':'text','text':'只回答：测试图片。'},{'type':'image_url','image_url':{'url':tiny}}]}],'max_completion_tokens':24,'thinking':{'type':'disabled'}}
        try:
            status,latency,response=_bounded_post(url,vision_key,payload,mimo='xiaomimimo.com' in vision_base.lower(),timeout=max(1.0,float(args.timeout)))
            content=((response.get('choices') or [{}])[0].get('message') or {}).get('content','') if response else ''
            row={'provider':'vision','model':vision_model,'http_status':status,'latency_ms':round(latency*1000),'response_present':bool(content),'network_reachable':True}
            if not 200 <= status < 300:
                row['error_type']='HTTPError'
            tests.append(row)
        except Exception as exc:
            tests.append({'provider':'vision','model':vision_model,'http_status':0,'latency_ms':0,'response_present':False,'network_reachable':False,'error_type':type(exc).__name__})
    online=bool(tests) and all(
        row.get('network_reachable')
        and 200 <= int(row.get('http_status', 0)) < 300
        and row.get('response_present')
        for row in tests
    )
    payload={'schema_version':1,'ok':online or not args.require_online,'online_verified':online,'tests':tests,'secrets_in_report':False}
    args.report.parent.mkdir(parents=True,exist_ok=True); args.report.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(payload,ensure_ascii=False,indent=2)); return 0 if payload['ok'] else 1
if __name__=='__main__': raise SystemExit(main())
