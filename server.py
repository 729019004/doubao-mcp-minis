#!/usr/bin/env python3
"""
server.py - 豆包多模态 MCP STDIO 服务 (Minis 专用版)
基于标准 JSON-RPC 2.0 协议，无需三方 MCP 复杂 SDK，纯 Python 标准库实现
适配 Minis 移动端沙盒，具有以下核心特质：
1. 拦截底层 stdout 重定向至 stderr，彻底杜绝日志污染 JSON-RPC 管道；
2. 生图自动生成并回传全量 Markdown 排版图片；
3. 视频生成后自动下载并提供原生可点击播放链接；
4. STDIO 模式随叫随到，天然免疫 iOS 后台清理，100% 保活。
"""
import sys
import os
import json
import asyncio
import aiohttp

# 保证本地 doubao_api 可直接导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/root")
try:
    from doubao_api import (
        chat as api_chat,
        generate_image as api_generate_image,
        generate_image_variation as api_generate_variation,
        generate_music as api_generate_music,
        generate_video as api_generate_video,
    )
except Exception as e:
    api_chat = None

MCP_TOOLS = [
    {
        "name": "doubao_chat",
        "description": "调用豆包大模型进行文本对话，支持普通模式和深度思考(思维链)模式。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "输入给豆包的问题或聊天内容"},
                "think": {"type": "boolean", "description": "是否开启深度思考模式（输出思考过程）", "default": False}
            },
            "required": ["text"]
        }
    },
    {
        "name": "doubao_image",
        "description": "调用豆包AI生成高质量图片（文生图），自动下载到作品目录并以Markdown排版直接输出。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "图片生成描述词（建议控制在10字以内，包含动作词更生动）"},
                "ratio": {
                    "type": "string",
                    "description": "图片比例：1:1, 16:9, 9:16, 4:3, 3:4",
                    "default": "1:1",
                    "enum": ["1:1", "16:9", "9:16", "4:3", "3:4"]
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "doubao_variation",
        "description": "调用豆包AI图生图（换装/变体），基于参考图片生成新图片并保存。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "参考图片本地绝对路径"},
                "prompt": {"type": "string", "description": "修改/换装提示词，如「女仆装，轻抚脸颊」", "default": ""},
                "ratio": {
                    "type": "string",
                    "description": "图片比例：1:1, 16:9, 9:16, 4:3, 3:4",
                    "default": "1:1"
                }
            },
            "required": ["image_path"]
        }
    },
    {
        "name": "doubao_video",
        "description": "调用豆包AI生成动态短视频（耗时约1~3分钟）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "视频场景与动作描述"},
                "ratio": {
                    "type": "string",
                    "description": "视频比例：16:9, 9:16, 1:1",
                    "default": "16:9"
                },
                "timeout": {
                    "type": "integer",
                    "description": "生成最长等待秒数",
                    "default": 300
                }
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "doubao_music",
        "description": "调用豆包AI生成音乐音频。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "音乐风格或歌词主题描述"},
                "genre": {"type": "string", "description": "音乐流派，如 pop, rock, jazz, edm"},
                "mood": {"type": "string", "description": "情绪，如 happy, sad, romantic, energetic"}
            },
            "required": ["prompt"]
        }
    }
]

REAL_STDOUT = sys.stdout
sys.stdout = sys.stderr

def send_response(resp):
    payload = json.dumps(resp, ensure_ascii=False)
    REAL_STDOUT.write(payload + "\n")
    REAL_STDOUT.flush()

async def handle_call_tool(tool_name, arguments):
    if not api_chat:
        return {"isError": True, "content": [{"type": "text", "text": "底层 doubao_api 模块未能正常加载"}]}
    
    try:
        if tool_name == "doubao_chat":
            text = arguments.get("text", "")
            think = arguments.get("think", False)
            res = await api_chat(text, deep_think=think)
            out = []
            if res.get("thinking"):
                out.append(f"【思考过程】\n{res['thinking']}")
            out.append(f"【回复】\n{res.get('text', '')}")
            return {"content": [{"type": "text", "text": "\n\n".join(out)}]}
        
        elif tool_name == "doubao_image":
            prompt = arguments.get("prompt", "")
            ratio = arguments.get("ratio", "1:1")
            saved = await api_generate_image(prompt, ratio=ratio)
            if not saved:
                return {"isError": True, "content": [{"type": "text", "text": "生图失败，未返回图片"}]}
            lines = [f"✅ 成功生成 {len(saved)} 张图片 (全量展示):"]
            for i, s in enumerate(saved):
                fpath = s['path']
                rel_url = fpath.replace("/var/minis/", "minis://")
                lines.append(f"\n![候选图 {i+1}]({rel_url})")
                lines.append(f"- 路径: {fpath} ({s['size']//1024}KB)")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        
        elif tool_name == "doubao_variation":
            img_path = arguments.get("image_path", "")
            if not os.path.exists(img_path):
                return {"isError": True, "content": [{"type": "text", "text": f"参考图文件不存在: {img_path}"}]}
            prompt = arguments.get("prompt", "")
            ratio = arguments.get("ratio", "1:1")
            saved = await api_generate_variation(img_path, prompt=prompt, ratio=ratio)
            if not saved:
                return {"isError": True, "content": [{"type": "text", "text": "图生图变体生成失败"}]}
            lines = [f"✅ 成功生成 {len(saved)} 张变体图片:"]
            for i, s in enumerate(saved):
                fpath = s['path']
                rel_url = fpath.replace("/var/minis/", "minis://")
                lines.append(f"\n![变体图 {i+1}]({rel_url})")
                lines.append(f"- 路径: {fpath} ({s['size']//1024}KB)")
            return {"content": [{"type": "text", "text": "\n".join(lines)}]}
        
        elif tool_name == "doubao_video":
            prompt = arguments.get("prompt", "")
            ratio = arguments.get("ratio", "16:9")
            timeout = arguments.get("timeout", 300)
            res = await api_generate_video(prompt, ratio=ratio, timeout=timeout)
            if res.get("videos"):
                lines = [f"✅ 成功生成 {len(res['videos'])} 个视频:"]
                save_dir = "/var/minis/shared/糖小织/作品" if os.path.exists("/var/minis") else os.path.expanduser("~/doubao_outputs")
                os.makedirs(save_dir, exist_ok=True)
                import time
                ts = int(time.time())
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as dl_sess:
                    for i, v in enumerate(res["videos"]):
                        v_url = v.get("url")
                        local_path = ""
                        if v_url:
                            try:
                                async with dl_sess.get(v_url) as v_resp:
                                    if v_resp.status == 200:
                                        v_data = await v_resp.read()
                                        local_path = os.path.join(save_dir, f"vid_{ts}_{i+1}.mp4")
                                        with open(local_path, "wb") as vf:
                                            vf.write(v_data)
                            except Exception as dl_e:
                                print(f"下载视频失败: {dl_e}", file=sys.stderr)
                        rel_v = local_path.replace("/var/minis/", "minis://") if local_path else ""
                        lines.append(f"\n▶️ [点击播放视频 {i+1}]({rel_v})")
                        lines.append(f"- 本地文件: {local_path or '未下载'}")
                        lines.append(f"- 封面: {v.get('cover')}")
                return {"content": [{"type": "text", "text": "\n".join(lines)}]}
            else:
                return {"isError": True, "content": [{"type": "text", "text": res.get("error", "视频生成失败")}]}
        
        elif tool_name == "doubao_music":
            prompt = arguments.get("prompt", "")
            genre = arguments.get("genre")
            mood = arguments.get("mood")
            res = await api_generate_music(prompt, genre=genre, mood=mood)
            if res.get("tracks"):
                lines = [f"✅ 成功生成 {len(res['tracks'])} 首音乐:"]
                for t in res["tracks"]:
                    lines.append(f"- 歌名: {t.get('title') or '未命名'}")
                    lines.append(f"- 时长: {t.get('duration')}s")
                    lines.append(f"- 音频链接: {t.get('audio_url')}")
                return {"content": [{"type": "text", "text": "\n".join(lines)}]}
            else:
                return {"isError": True, "content": [{"type": "text", "text": res.get("error", "音乐生成失败")}]}
        
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"未知工具: {tool_name}"}]}
            
    except Exception as e:
        return {"isError": True, "content": [{"type": "text", "text": f"执行错误: {str(e)}"}]}

async def main():
    loop = asyncio.get_event_loop()
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line = await reader.readline()
        if not line:
            break
        raw_str = line.decode("utf-8").strip()
        if not raw_str:
            continue
        try:
            req = json.loads(raw_str)
        except Exception:
            continue
        
        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": False}
                    },
                    "serverInfo": {
                        "name": "doubao-mcp",
                        "version": "1.0.0"
                    }
                }
            })
        elif method == "notifications/initialized":
            pass
        elif method == "ping":
            send_response({"jsonrpc": "2.0", "id": req_id, "result": {}})
        elif method == "tools/list":
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": MCP_TOOLS
                }
            })
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            result = await handle_call_tool(tool_name, tool_args)
            send_response({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": result
            })
        else:
            if req_id is not None:
                send_response({
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    }
                })

if __name__ == "__main__":
    asyncio.run(main())
