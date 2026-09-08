#!/usr/bin/env python3
"""
doubao_api.py - 豆包多模态 API 客户端 (Minis 深度定制与抗超时强化版)
支持：对话(Chat)、深度思考(Deep Think)、文生图(Image)、图生图换装(Variation)、视频(Video)、音乐(Music)
"""
import asyncio
import json
import os
import sys
import uuid
import argparse
from urllib.parse import urlencode

import aiohttp

# ========== 核心路径与配置 ==========
SESSION_FILE = os.environ.get("DOUBAO_SESSION_FILE", os.path.expanduser("~/.doubao_session.json"))
if not os.path.exists(SESSION_FILE):
    # Minis 环境回退路径
    if os.path.exists("/root/.doubao_session.json"):
        SESSION_FILE = "/root/.doubao_session.json"

DEFAULT_SAVE_DIR = os.environ.get("DOUBAO_SAVE_DIR", "/var/minis/shared/糖小织/作品")
if not os.path.exists("/var/minis"):
    DEFAULT_SAVE_DIR = os.path.expanduser("~/doubao_outputs")

BASE_URL = "https://www.doubao.com"
CHROME_VERSION = "131.0.6778.140"

# ========== 工具函数 ==========

def load_cookies():
    if not os.path.exists(SESSION_FILE):
        return {}
    with open(SESSION_FILE) as f:
        return json.load(f).get("cookies", {})

def security_params():
    return {
        "aid": "582478", "real_aid": "582478",
        "device_id": "714003710229497",
        "web_id": "7604137868021548590",
        "device_platform": "web", "language": "zh",
        "region": "CN", "sys_region": "CN",
        "pkg_type": "release_version", "version_code": "20800",
        "pc_version": "2.1.7", "chromium_version": "6778.140",
        "client_platform": "pc_client",
        "fp": "verify_mlcfw5f7_TPq0YmFD_NrsC_4RuQ_BJPg_M5W7i58I7wV0",
        "web_tab_id": str(uuid.uuid4()),
    }

def get_headers():
    return {
        "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/{CHROME_VERSION} Safari/537.36",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
        "Referer": f"{BASE_URL}/chat",
    }

async def sse_post(payload, timeout=120, max_retries=3):
    """发送 SSE 请求并返回原始文本，所有重试信息均定向至 stderr 避免污染 stdout"""
    cookies = load_cookies()
    url = f"{BASE_URL}/samantha/chat/completion?{urlencode(security_params())}"
    
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession(
                cookies=cookies,
                timeout=aiohttp.ClientTimeout(total=timeout),
                headers=get_headers(),
            ) as session:
                async with session.post(
                    url,
                    data=json.dumps(payload, ensure_ascii=False),
                    headers={"Accept": "text/event-stream", "Agw-Js-Conv": "str"},
                ) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"API错误 {resp.status}: {error[:200]}")
                    raw = (await resp.read()).decode("utf-8", errors="replace")
                    
                    if '"code":710020702' in raw:
                        if attempt < max_retries - 1:
                            wait = 5 * (attempt + 1)
                            print(f"⚠️ API 临时错误，{wait}秒后重试...", file=sys.stderr)
                            await asyncio.sleep(wait)
                            continue
                        else:
                            raise Exception("API 系统错误（710020702），请稍后重试")
                    
                    return raw
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"⚠️ 请求失败，{wait}秒后重试: {e}", file=sys.stderr)
                await asyncio.sleep(wait)
            else:
                raise

def parse_sse_events(raw):
    """解析 SSE 事件"""
    events = []
    for block in raw.split("\n\n"):
        if not block.strip():
            continue
        data_str = ""
        for line in block.strip().split("\n"):
            if line.startswith("data:"):
                data_str = line[5:].strip()
        if not data_str or data_str == "[DONE]":
            continue
        try:
            events.append(json.loads(data_str))
        except json.JSONDecodeError:
            pass
    return events

# ========== 功能 1: 聊天 (含 2018/2071 代码块新协议支持) ==========

async def chat(text, deep_think=False):
    """发送聊天消息"""
    payload = {
        "messages": [{
            "content": json.dumps({"text": text}, ensure_ascii=False),
            "content_type": 2001,
            "attachments": [], "references": [],
        }],
        "completion_option": {
            "is_regen": False, "with_suggest": True,
            "need_create_conversation": True, "launch_stage": 1,
            "memory_type": 2, "message_from": 0,
            "use_deep_think": deep_think,
        },
        "evaluate_option": {"web_ab_params": ""},
        "local_conversation_id": str(uuid.uuid4()),
        "local_message_id": str(uuid.uuid4()),
    }
    
    raw = await sse_post(payload)
    events = parse_sse_events(raw)
    
    result_text = ""
    thinking_text = ""
    
    for event in events:
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        msg = ed.get("message", {})
        ct = msg.get("content_type", 0)
        content_str = msg.get("content", {})
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
        except:
            continue
        
        # 2018: 常规文本; 2071: 代码块与工程文本
        if ct in (2001, 2003, 2018, 2071, 10000):
            result_text += content.get("text", "")
        elif ct == 2008:
            thinking_text += content.get("think", "")
            result_text += content.get("text", "")
        elif ct == 10040:
            thinking_text += content.get("think", "")
    
    return {"text": result_text, "thinking": thinking_text}

# ========== 功能 2: 文生图 (asyncio.gather 高并发拉取大图) ==========

async def generate_image(prompt, ratio="1:1", save_dir=DEFAULT_SAVE_DIR):
    """生成图片，使用并发下载杜绝串行超时与截断"""
    content_dict = {"text": prompt}
    if ratio:
        content_dict["ratio"] = ratio
    
    payload = {
        "messages": [{
            "content": json.dumps(content_dict, ensure_ascii=False),
            "content_type": 2009,
            "attachments": [], "references": [],
            "skill": {"skill_type": 3, "skill_type_no_default": 3, "skill_id": "3", "skill_id_no_default": "3"},
        }],
        "completion_option": {
            "is_regen": False, "with_suggest": True,
            "need_create_conversation": True, "launch_stage": 1,
            "memory_type": 2, "message_from": 0,
            "use_deep_think": False, "action_bar_skill_id": 3,
        },
        "evaluate_option": {"web_ab_params": ""},
        "local_conversation_id": str(uuid.uuid4()),
        "local_message_id": str(uuid.uuid4()),
    }
    
    raw = await sse_post(payload, timeout=120)
    events = parse_sse_events(raw)
    
    image_urls = []
    for event in events:
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        msg = ed.get("message", {})
        if msg.get("content_type") != 2010:
            continue
        content_str = msg.get("content", {})
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
        except:
            continue
        for item in content.get("data", []):
            if isinstance(item, dict):
                ori = item.get("image_ori", {}) or {}
                url = ori.get("url", "")
                if url:
                    image_urls.append(url)
    
    if not image_urls:
        return []
    
    os.makedirs(save_dir, exist_ok=True)
    import time
    ts = int(time.time())

    async def fetch_one(session, url, idx):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    fpath = os.path.join(save_dir, f"img_{ts}_{idx+1}.png")
                    with open(fpath, "wb") as f:
                        f.write(data)
                    return {"path": fpath, "size": len(data)}
        except Exception as e:
            print(f"下载图片 {idx+1} 失败: {e}", file=sys.stderr)
        return None

    timeout_client = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout_client) as session:
        tasks = [fetch_one(session, url, i) for i, url in enumerate(image_urls)]
        results = await asyncio.gather(*tasks)
        saved = [r for r in results if r is not None]
    
    return saved

# ========== 功能 3: 图生图变体 (Variation) ==========

async def upload_image(image_path, max_retries=3):
    """上传图片到豆包，返回 ref_image_key"""
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    filename = os.path.basename(image_path)
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "png"
    cookies = load_cookies()
    
    for attempt in range(max_retries):
        try:
            params = security_params()
            upload_url = f"{BASE_URL}/samantha/pages/upload_image?{urlencode(params)}"
            form = aiohttp.FormData()
            form.add_field("data", image_bytes, filename=filename, content_type=f"image/{ext}")
            form.add_field("file_type", ext)
            
            upload_headers = {
                "User-Agent": get_headers()["User-Agent"],
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/chat",
                "x-tt-passport-csrf-token": cookies.get("passport_csrf_token", "") or cookies.get("passport_csrf_token_default", ""),
            }
            
            async with aiohttp.ClientSession(cookies=cookies, headers=upload_headers, timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(upload_url, data=form) as resp:
                    if resp.status != 200:
                        raise Exception(f"上传失败 ({resp.status})")
                    body = await resp.json()
                    if body.get("code") != 0:
                        raise Exception(f"上传错误: {body.get('msg', body)}")
                    uri_short = body["data"]["uri"]
            
            file_url_endpoint = f"{BASE_URL}/alice/message/get_file_url?{urlencode(security_params())}"
            async with aiohttp.ClientSession(cookies=cookies, timeout=aiohttp.ClientTimeout(total=30), headers=get_headers()) as session:
                async with session.post(file_url_endpoint, json={"uris": [uri_short], "type": "image", "format": ext, "expire_second": 3600}) as resp:
                    body = await resp.json()
                    file_urls = body.get("data", {}).get("file_urls", [])
                    if file_urls:
                        return file_urls[0]["uri"]
            return uri_short
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"⚠️ 上传失败，{wait}秒后重试: {e}", file=sys.stderr)
                await asyncio.sleep(wait)
            else:
                raise

async def generate_image_variation(image_path, prompt="", ratio="1:1", save_dir=DEFAULT_SAVE_DIR):
    """基于参考图生成变体"""
    print(f"📤 正在上传参考图片: {image_path}", file=sys.stderr)
    ref_key = await upload_image(image_path)
    print(f"✅ 图片已上传", file=sys.stderr)
    
    content_dict = {"text": prompt or "保持原图风格，生成类似图片"}
    if ratio:
        content_dict["ratio"] = ratio
    
    payload = {
        "messages": [{
            "content": json.dumps(content_dict, ensure_ascii=False),
            "content_type": 2009,
            "attachments": [{"type": "image", "key": ref_key, "extra": {"refer_types": "overall"}}],
            "references": [],
            "skill": {"skill_type": 3, "skill_type_no_default": 3, "skill_id": "3", "skill_id_no_default": "3"},
        }],
        "completion_option": {
            "is_regen": False, "with_suggest": True,
            "need_create_conversation": True, "launch_stage": 1,
            "memory_type": 2, "message_from": 0,
            "use_deep_think": False, "action_bar_skill_id": 3,
        },
        "evaluate_option": {"web_ab_params": ""},
        "local_conversation_id": str(uuid.uuid4()),
        "local_message_id": str(uuid.uuid4()),
    }
    
    raw = await sse_post(payload, timeout=120)
    events = parse_sse_events(raw)
    
    image_urls = []
    for event in events:
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        msg = ed.get("message", {})
        if msg.get("content_type") != 2010:
            continue
        content_str = msg.get("content", {})
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
        except:
            continue
        for item in content.get("data", []):
            if isinstance(item, dict):
                ori = item.get("image_ori", {}) or {}
                url = ori.get("url", "")
                if url:
                    image_urls.append(url)
    
    if not image_urls:
        return []
    
    os.makedirs(save_dir, exist_ok=True)
    import time
    ts = int(time.time())

    async def fetch_one(session, url, idx):
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    fpath = os.path.join(save_dir, f"var_{ts}_{idx+1}.png")
                    with open(fpath, "wb") as f:
                        f.write(data)
                    return {"path": fpath, "size": len(data)}
        except Exception as e:
            print(f"下载图片 {idx+1} 失败: {e}", file=sys.stderr)
        return None

    timeout_client = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout_client) as session:
        tasks = [fetch_one(session, url, i) for i, url in enumerate(image_urls)]
        results = await asyncio.gather(*tasks)
        saved = [r for r in results if r is not None]
    
    return saved

# ========== 功能 4: 视频生成 (带 task_id 提取与异步流) ==========

async def generate_video(prompt, ratio="16:9", timeout=300):
    """生成视频"""
    content_dict = {"text": prompt}
    if ratio:
        content_dict["ratio"] = ratio
    
    payload = {
        "messages": [{
            "content": json.dumps(content_dict, ensure_ascii=False),
            "content_type": 2020,
            "attachments": [], "references": [],
            "skill": {"skill_type": 17, "skill_type_no_default": 17, "skill_id": "17", "skill_id_no_default": "17"},
        }],
        "completion_option": {
            "is_regen": False, "with_suggest": True,
            "need_create_conversation": True, "launch_stage": 1,
            "memory_type": 2, "message_from": 0,
            "use_deep_think": False, "action_bar_skill_id": 17,
        },
        "evaluate_option": {"web_ab_params": ""},
        "local_conversation_id": str(uuid.uuid4()),
        "local_message_id": str(uuid.uuid4()),
    }
    
    print("⏳ 正在提交视频生成请求...", file=sys.stderr)
    raw = await sse_post(payload, timeout=60)
    
    task_id = None
    videos = []
    for event in parse_sse_events(raw):
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        fin = ed.get("fin_reason", {})
        if fin.get("reason") == 1:
            task_id = fin.get("async_task", {}).get("id")
            if task_id:
                break
        msg = ed.get("message", {})
        if msg.get("content_type") == 2021:
            task_id = msg.get("id") or ed.get("message_id")
            if task_id:
                break
    
    if not task_id:
        return {"error": "未能获取任务 ID，可能官方网关暂时拥堵"}
    
    print(f"📋 任务 ID: {task_id}", file=sys.stderr)
    print(f"⏳ 等待视频生成完成（最长 {timeout} 秒）...", file=sys.stderr)
    
    poll_url = f"{BASE_URL}/samantha/chat/async/stream?{urlencode(security_params())}"
    poll_body = json.dumps({"task_id": task_id, "event_id": 0})
    cookies = load_cookies()
    
    try:
        async with aiohttp.ClientSession(cookies=cookies, timeout=aiohttp.ClientTimeout(total=timeout), headers=get_headers()) as session:
            async with session.post(poll_url, data=poll_body, headers={"Accept": "text/event-stream", "Agw-Js-Conv": "str"}) as resp:
                raw = (await resp.read()).decode("utf-8", errors="replace")
    except Exception as e:
        return {"error": f"轮询视频失败: {e}", "task_id": task_id}
    
    for event in parse_sse_events(raw):
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        msg = ed.get("message", {})
        if msg.get("content_type") != 2021:
            continue
        content_str = msg.get("content", {})
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
        except:
            continue
        for item in content.get("data", []):
            if isinstance(item, dict):
                video_url = item.get("video_url", "") or item.get("url", "")
                if video_url:
                    videos.append({
                        "url": video_url,
                        "duration": item.get("duration", 0),
                        "cover": item.get("cover_url", ""),
                    })
    
    return {"videos": videos, "task_id": task_id}

# ========== 功能 5: 音乐生成 ==========

async def generate_music(prompt, **kwargs):
    """生成音乐"""
    content_dict = {"text": prompt}
    for key in ["lyric", "genre", "mood", "gender", "theme"]:
        if kwargs.get(key):
            content_dict[key] = kwargs[key]
    
    payload = {
        "messages": [{
            "content": json.dumps(content_dict, ensure_ascii=False),
            "content_type": 2005,
            "attachments": [], "references": [],
            "skill": {"skill_type": 9, "skill_type_no_default": 9, "skill_id": "9", "skill_id_no_default": "9"},
        }],
        "completion_option": {
            "is_regen": False, "with_suggest": True,
            "need_create_conversation": True, "launch_stage": 1,
            "memory_type": 2, "message_from": 0,
            "use_deep_think": False, "action_bar_skill_id": 9,
        },
        "evaluate_option": {"web_ab_params": ""},
        "local_conversation_id": str(uuid.uuid4()),
        "local_message_id": str(uuid.uuid4()),
    }
    
    raw = await sse_post(payload, timeout=120)
    tracks = []
    for event in parse_sse_events(raw):
        if event.get("event_type") != 2001:
            continue
        ed_str = event.get("event_data", "")
        try:
            ed = json.loads(ed_str) if isinstance(ed_str, str) else ed_str
        except:
            continue
        msg = ed.get("message", {})
        if msg.get("content_type") != 2006:
            continue
        content_str = msg.get("content", {})
        try:
            content = json.loads(content_str) if isinstance(content_str, str) else content_str
        except:
            continue
        for task in content.get("data", {}).get("tasks", []):
            if isinstance(task, dict):
                audio_url = ""
                vm_str = task.get("video_model", "")
                if vm_str:
                    try:
                        import base64
                        vm = json.loads(vm_str) if isinstance(vm_str, str) else vm_str
                        vlist = vm.get("video_list", {})
                        for _q, vinfo in vlist.items():
                            main_b64 = vinfo.get("main_url", "")
                            if main_b64:
                                audio_url = base64.b64decode(main_b64).decode("utf-8", errors="replace")
                                break
                    except:
                        pass
                cover_url = (task.get("cover", {}) or {}).get("image_ori", {}).get("url", "")
                tracks.append({
                    "title": task.get("title", ""),
                    "audio_url": audio_url,
                    "duration": task.get("duration", 0),
                    "lyrics": task.get("lyric", ""),
                    "cover_url": cover_url,
                })
    return {"tracks": tracks}

# ========== CLI 入口 ==========

async def main():
    parser = argparse.ArgumentParser(description="豆包多模态 API 客户端 (Minis 特别版)")
    sub = parser.add_subparsers(dest="command", help="子命令")
    
    # 聊天
    chat_p = sub.add_parser("chat", help="文本对话")
    chat_p.add_argument("text", help="内容")
    chat_p.add_argument("--think", action="store_true", help="深度思考")
    
    # 文生图
    img_p = sub.add_parser("image", help="文生图")
    img_p.add_argument("prompt", help="提示词")
    img_p.add_argument("--ratio", default="1:1", help="比例 1:1, 16:9, 9:16, 4:3, 3:4")
    
    # 图生图
    var_p = sub.add_parser("variation", help="图生图")
    var_p.add_argument("image", help="参考图路径")
    var_p.add_argument("--prompt", default="", help="修改词")
    var_p.add_argument("--ratio", default="1:1", help="比例")
    
    # 视频
    vid_p = sub.add_parser("video", help="生成视频")
    vid_p.add_argument("prompt", help="提示词")
    vid_p.add_argument("--ratio", default="16:9", help="比例")
    vid_p.add_argument("--timeout", type=int, default=300, help="超时时间")
    
    # 音乐
    mus_p = sub.add_parser("music", help="生成音乐")
    mus_p.add_argument("prompt", help="风格或歌词")
    mus_p.add_argument("--genre", help="流派")
    mus_p.add_argument("--mood", help="情绪")
    
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    if args.command == "chat":
        res = await chat(args.text, args.think)
        if res.get("thinking"):
            print(f"💭 思考:\n{res['thinking']}\n")
        print(f"💬 回复:\n{res.get('text', '')}")
    elif args.command == "image":
        saved = await generate_image(args.prompt, args.ratio)
        if saved:
            print(f"✅ 成功生成 {len(saved)} 张图片:")
            for s in saved:
                print(f"   📁 {s['path']} ({s['size']//1024}KB)")
        else:
            print("❌ 生图失败")
    elif args.command == "variation":
        saved = await generate_image_variation(args.image, args.prompt, args.ratio)
        if saved:
            print(f"✅ 成功生成 {len(saved)} 张变体图片:")
            for s in saved:
                print(f"   📁 {s['path']} ({s['size']//1024}KB)")
        else:
            print("❌ 变体生成失败")
    elif args.command == "video":
        res = await generate_video(args.prompt, args.ratio, args.timeout)
        if res.get("videos"):
            print(f"✅ 生成 {len(res['videos'])} 个视频:")
            for v in res["videos"]:
                print(f"   🎬 {v['url']}")
        else:
            print(f"❌ {res.get('error', '生成失败')}")
    elif args.command == "music":
        res = await generate_music(args.prompt, genre=args.genre, mood=args.mood)
        if res.get("tracks"):
            print(f"✅ 生成 {len(res['tracks'])} 首音乐:")
            for t in res["tracks"]:
                print(f"   🎵 {t['title']} - {t['audio_url']}")
        else:
            print("❌ 音乐生成失败")

if __name__ == "__main__":
    asyncio.run(main())
