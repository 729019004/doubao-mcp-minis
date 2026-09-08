# doubao-mcp-minis

> 🚀 **豆包多模态 API & 极简轻量级 MCP STDIO 服务（Minis / iOS 沙盒特别定制版）**  
> 免 API Key、免三方笨重依赖、基于浏览器 Session Cookie 免费驱动豆包全模态能力！

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Platform: Minis / iOS](https://img.shields.io/badge/Platform-Minis%20%7C%20iOS%20%7C%20iSH-green.svg)]()

---

## ⚡ 30 秒极速上手（新手保姆级三步走）

如果你是 **Minis App** 用户，无需研究底层代码，直接打开 Minis 的 **Terminal（终端）**，按顺序复制以下三步命令即可！

### 第一步：一键拉取项目代码与挂载技能手册
在 Minis 终端中粘贴执行：
```bash
# 1. 克隆项目到推荐的持久化项目目录
git clone https://github.com/729019004/doubao-mcp-minis.git /var/minis/shared/项目/doubao-mcp

# 2. 一键把专属提示词操作手册挂载进你的 AI 大脑
mkdir -p /var/minis/skills/doubao2api
cp /var/minis/shared/项目/doubao-mcp/SKILL.md /var/minis/skills/doubao2api/SKILL.md
```

---

### 第二步：配置你的登录 Cookie（免 Key 核心）
我们在电脑浏览器登录一次豆包，把鉴权 Cookie 复制出来即可（一次配置，长期有效）：

1. 在电脑浏览器（Chrome / Edge）打开并登录 [豆包官网 (doubao.com)](https://www.doubao.com)；
2. 按键盘 **`F12`**（或右键 -> 检查）打开开发者工具；
3. 切换到 **Application（应用）** -> 左侧展开 **Cookies** -> 点击 `https://www.doubao.com`；
4. 找到并复制以下三个核心值：
   - `sessionid`
   - `ttwid`
   - `passport_csrf_token`
5. 回到 Minis 终端，执行下面这行命令创建配置文件（替换成你自己的值）：
```bash
cat << 'EOF' > /root/.doubao_session.json
{
  "cookies": {
    "sessionid": "填入你的sessionid",
    "ttwid": "填入你的ttwid",
    "passport_csrf_token": "填入你的passport_csrf_token"
  }
}
EOF
```

---

### 第三步：一键注册 MCP 服务并测试
在 Minis 终端中执行注册：
```bash
# 1. 注册进入系统 MCP 服务
minis-mcp-cli add --name doubao-mcp \
  --command python3 \
  --args "/var/minis/shared/项目/doubao-mcp/server.py" \
  --note "豆包多模态生成中心（免Key，生图/变体/视频/音乐/深度思考）"

# 2. 刷新让系统发现 5 个新工具
minis-mcp-cli tools doubao-mcp --refresh

# 3. 冒烟测试：测试对话
minis-mcp-cli call doubao-mcp doubao_chat --input '{"text":"你好，请用一句话介绍你自己"}'
```
🎉 当终端返回 `【回复】我是字节跳动自研的AI助手豆包...` 时，说明已经大功告成！  
现在你的 Minis AI 已经掌握了随时调用豆包文生图、图生图换装、做视频、做音乐的全部本领！

---

## 🛠️ 工具箱矩阵（5 大 MCP Tools）

| 工具名 | 功能说明 | 核心参数说明 |
| :--- | :--- | :--- |
| **`doubao_image`** | 高清文生图，自动下载并全量 Markdown 直显所有候选大图 | `prompt` (提示词), `ratio` (1:1, 16:9, 9:16, 4:3, 3:4) |
| **`doubao_variation`**| 图生图 / 换装变体，基于本地参考底图精准锁定人脸特征 | `image_path` (参考底图绝对路径), `prompt` (换装词), `ratio` |
| **`doubao_chat`** | 文本对话，支持普通问答与深度思考（思维链）模式 | `text` (输入问题), `think` (true 开启思维链) |
| **`doubao_video`** | 动态短视频生成，自动下载落盘并返回 App 原生播放直链 | `prompt` (运动场景), `ratio`, `timeout` |
| **`doubao_music`** | 音乐与音效生成，支持自定义流派与情绪 | `prompt` (主题歌词), `genre` (流派), `mood` (情绪) |

---

## 💻 命令行独立使用 (CLI 模式)
除了作为 MCP 工具供 Agent 调用外，你也可以在终端直接当 CLI 工具使用：
```bash
cd /var/minis/shared/项目/doubao-mcp

# 1. 普通聊天与深度思考
python3 doubao_api.py chat "今天过得怎么样？"
python3 doubao_api.py chat "分析黄金近期走势" --think

# 2. 文生图（生成多张候选大图自动保存至作品目录）
python3 doubao_api.py image "一只可爱的小橘猫躺在阳光下" --ratio 16:9

# 3. 图生图换装
python3 doubao_api.py variation /path/to/photo.jpg --prompt "女仆装，轻抚脸颊" --ratio 1:1
```

---

## ✨ 核心特性与技术亮点

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

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 开源。  
作者 / 维护者：**重装小兔R4C** ([@729019004](https://github.com/729019004))  
仅供个人技术研究、学习与移动端 Agent 生态交流使用，请勿用于非法商业用途。
