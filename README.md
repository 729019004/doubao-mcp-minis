# doubao-mcp-minis

> 🚀 **豆包多模态 API & 极简轻量级 MCP STDIO 服务（Minis / iOS 沙盒特别定制版）**  
> 免 API Key、免三方笨重依赖、基于浏览器 Session Cookie 免费驱动豆包全模态能力！

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform: Minis / iOS](https://img.shields.io/badge/Platform-Minis%20%7C%20iOS%20%7C%20iSH-green.svg)]()

---

## ✨ 核心特性（专为 Minis 移动端沙盒痛点研发）

1. **天然免疫 iOS 后台杀进程（100% 保活）**：
   - 抛弃易被 iOS 系统 Jetsam 清理的常驻后台孤儿进程；
   - 采用标准 **JSON-RPC 2.0 STDIO 管道模式**，由 Minis 原生拉起生命周期托管，用完即收、随叫随到。
2. **零额外依赖（纯 Python 标准库骨架）**：
   - MCP Server 纯依靠 `asyncio`、`sys`、`json` 实现，彻底摆脱官方 SDK 复杂编译和依赖地狱。
3. **彻底杜绝 JSON-RPC 管道污染**：
   - 实施全局 `sys.stdout = sys.stderr` 拦截，所有底层调试与重试日志均自动导向 `stderr`，仅有协议回包走专用的 `REAL_STDOUT`。
4. **`asyncio.gather` 并发极速下载（抗超时防御）**：
   - 一次性生成 3~4 张高清大图（单张 1.5MB+）时，自动使用协程并发下载 + 60s 显式超时防护，彻底杜绝串行拉取导致的数据截断。
5. **全量图片与视频直显支持**：
   - 生图工具直接内嵌回传全部候选图片的 Markdown 预览格式；
   - 视频生成自动落盘本地，并返回带有 `minis://` 原生播放链接的成果卡片。
6. **2026 最新协议适配**：
   - 完美适配豆包最新返回格式：常规文本 `2018`、代码/工程输出 `2071`。

---

## 🛠️ 工具箱矩阵（5 大 MCP Tools）

| 工具名 | 功能说明 | 核心参数 |
| :--- | :--- | :--- |
| **`doubao_image`** | 高清文生图，自动全量下载并展示所有候选大图 | `prompt`, `ratio` (1:1, 16:9, 9:16, 4:3, 3:4) |
| **`doubao_variation`**| 图生图 / 换装变体，基于参考底图精准锁定人脸特征 | `image_path`, `prompt`, `ratio` |
| **`doubao_chat`** | 文本对话，支持普通问答与深度思考（思维链）模式 | `text`, `think` (true/false) |
| **`doubao_video`** | 动态短视频生成，自动下载落盘并返回播放直链 | `prompt`, `ratio`, `timeout` |
| **`doubao_music`** | 音乐与音效生成，支持自定义流派与情绪 | `prompt`, `genre`, `mood` |

---

## 🚀 快速上手与集成指引

### 1. 配置 Session Cookie
在浏览器登录 [豆包网页端](https://www.doubao.com)，复制 Cookies（主要是 `sessionid`, `ttwid`, `passport_csrf_token`），保存到 `~/.doubao_session.json`：
```json
{
  "cookies": {
    "sessionid": "你的sessionid",
    "ttwid": "你的ttwid",
    "passport_csrf_token": "你的passport_csrf_token"
  }
}
```

### 2. 在 Minis 中一键注册 MCP 服务
```bash
minis-mcp-cli add --name doubao-mcp \
  --command python3 \
  --args "$(pwd)/server.py" \
  --note "豆包多模态生成中心（免Key，生图/变体/视频/音乐/深度思考）"
```

### 3. 刷新并验证连通性
```bash
# 刷新工具发现
minis-mcp-cli tools doubao-mcp --refresh

# 测试聊天
minis-mcp-cli call doubao-mcp doubao_chat --input '{"text":"你好，请用一句话介绍你自己"}'

# 测试文生图
minis-mcp-cli call doubao-mcp doubao_image --input '{"prompt":"一只可爱的小橘猫躺在草地上","ratio":"1:1"}'
```

### 4. 命令行独立使用 (CLI 模式)
无需通过 MCP，也可以直接通过 `doubao_api.py` 执行：
```bash
# 聊天
python3 doubao_api.py chat "今天过得怎么样？"

# 深度思考
python3 doubao_api.py chat "分析黄金近期走势" --think

# 文生图
python3 doubao_api.py image "一只可爱的小橘猫躺在阳光下" --ratio 16:9

# 图生图变体换装
python3 doubao_api.py variation /path/to/photo.jpg --prompt "女仆装，轻抚脸颊" --ratio 1:1
```

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。
仅供个人技术研究、学习与移动端 Agent 生态交流使用，请勿用于非法商业用途。
