# 小智电脑助手（商业版工程骨架）

这是一个面向 Windows 的“小智 + 本地电脑执行端”完整工程。目标是：客户安装一个 EXE，首次双击填写 **小智 MCP 接入地址 + 自己的 AI API**，之后让小智通过语音完成 Word、Excel、PDF、网页、微信、文件和 Windows 操作。

> 版本：0.1.0。当前交付的是可构建、可扩展的完整工程源码和 Windows 构建链。由于生成环境不是 Windows，本仓库附带 Windows GitHub Actions/本地构建脚本来产出并验证最终 EXE。

## 最重要的架构

```text
用户说话
  ↓
小智（语音入口）
  ↓
小智后台 MCP 路由
  ↓
desktop_agent(instruction)
  ↓
用户在客户端填写的 AI API
(OpenAI / DeepSeek / 豆包方舟 / 自定义兼容 API)
  ↓
本地 Agent 自主调用：
文件 / Word / Excel / PDF / 浏览器 DOM / Windows UIA / 微信 / OCR
  ↓
Windows 真正执行
```

### “不用小智后台模型”是什么意思？

小智的 **MCP WebSocket 接入地址仍然需要小智后台提供**，因为这是小智把语音任务送到电脑的传输/路由通道。

但本工程提供一个统一 `desktop_agent(instruction)` 工具。建议在小智智能体提示词中要求“电脑任务优先调用 desktop_agent”。一旦任务进入这个工具，后续规划、分析、写作和工具选择全部使用客户在客户端填写的 API。这样可把小智后台模型的作用压缩到最小的“识别这是电脑任务并转交”。

如果要做到连这一步也完全绕过小智后台 LLM，就不是普通 MCP 客户端改造了，而需要同时改小智服务端/音频协议。

## 已实现模块

### 1. 自定义 AI API

首次运行 GUI 可选择：

- OpenAI（预设 `https://api.openai.com/v1`）
- DeepSeek（预设 `https://api.deepseek.com`）
- 豆包方舟（预设 `https://ark.cn-beijing.volces.com/api/v3`）
- 自定义 OpenAI 兼容 API

模型名可自由修改。接口模式支持：

- `auto`：优先 Responses API，不兼容时回退 Chat Completions
- `responses`
- `chat`

API Key 不写入普通 JSON，Windows 下使用 DPAPI 加密保存到当前 Windows 用户上下文。

### 2. Word

- 直接生成 `.docx`，不打开 Word、不模拟打字
- AI 写材料并直接保存 Word
- 读取 Word
- AI 修改 Word 并另存修改版
- 默认中文标题/正文基础排版

典型语音：

> 帮我写一份安全生产工作总结，1500 字，正式一点，做成 Word 放桌面。

### 3. Excel

- pandas/openpyxl 本地读取
- 统计行列、缺失值、数值描述、合计、Top 分类
- 只把“统计摘要”交给 AI，不默认上传整张大表
- AI 给出结论/异常/建议
- 可生成 Word 数据分析报告

典型语音：

> 分析桌面的八月份销售表，找出下降最大的区域，并生成分析报告。

### 4. PDF

- 读取可提取文本
- AI 总结/问答
- 关键词检索上下文
- 多 PDF 合并

扫描 PDF 可结合 OCR 继续扩展为逐页 OCR。

### 5. 网页自动化

不把 OCR 当主路径。客户端启动独立 Chrome/Edge 配置目录并通过 DevTools 协议读取/操作网页：

- 打开 URL
- Bing / 百度 / Google 搜索
- 读取当前网页 DOM 正文
- 使用自己的 AI API 总结网页
- 按可见文字点击按钮/链接
- 按标签/placeholder/name 填输入框
- 提取 HTML 表格
- 下载按钮点击

优点：大多数网页操作不需要截图、OCR、坐标。

### 6. Windows UI Automation

通过 pywinauto/UIA：

- 列出窗口
- 激活窗口
- 最大化/最小化/恢复/关闭
- 移动/缩放
- 获取 UI Automation 控件树
- 按控件名称点击
- 启动程序

优先级建议：

```text
直接 API/文件操作 > DOM/UIA > 快捷键 > 本地 OCR > 坐标点击
```

### 7. 微信助手

当前实现采用桌面微信的 UIA + 快捷键方案：

1. `prepare_wechat_message(contact, message)` 只准备消息，返回确认提示和 pending id
2. 用户明确确认后才允许 `wechat_confirm_send(pending_id)`
3. 激活微信 → Ctrl+F 搜联系人 → 粘贴 → Enter → 粘贴消息 → Enter
4. `read_wechat_ui()` 可读取当前微信 UIA 可访问文本

微信客户端 UI 版本变化会影响自动化，因此商业发布前必须在目标微信版本上做回归测试。

### 8. OCR / 屏幕

- `RapidOCR + ONNX Runtime` 本地 OCR
- 返回文字和中心坐标
- 全屏截图
- 如果所选模型支持视觉，可把截图交给自己的模型解释

OCR 被设计为兜底，不是主要交互方式。

### 9. 文件/系统

- 搜索文件
- 列目录
- 文本文件创建
- 复制/移动
- 删除（强制确认语义）
- 按扩展名整理目录（确认）
- CPU/内存/磁盘状态
- 系统音量
- 系统命令（确认）

### 10. 商业化壳子

- PySide6 设置界面
- Windows 系统托盘
- 开机自启
- 自动重连小智 MCP
- 一键诊断
- 操作日志 SQLite
- 更新 manifest + SHA256 下载框架
- PyInstaller 单 EXE 构建
- Inno Setup 安装包
- GitHub Actions Windows 自动构建

## 用户安装后的流程

客户不需要安装 Python。

1. 安装 `XiaozhiDesktopAssistant-Setup-x.x.x.exe`
2. 双击“**小智电脑助手**”
3. 在“连接”页粘贴小智后台提供的 `wss://...token=...` MCP 地址
4. 在“AI API”页选择 OpenAI / DeepSeek / 豆包或自定义
5. 填 API Key 和模型名，点“测试连接”
6. 保存并连接
7. 软件可最小化到托盘/开机自启

推荐给小智智能体增加的提示：见 `xiaozhi-agent-prompt.txt`。

## 开发者：Windows 本机构建

要求仅针对开发/构建机器，客户不需要：

- Windows 10/11 x64
- Python 3.12
- 可选 Inno Setup 6

双击：

```bat
build_windows.bat
```

它会：

1. 创建 `.venv`
2. 安装构建依赖
3. 跑测试
4. PyInstaller 生成 `dist/XiaozhiDesktopAssistant.exe`
5. 如果安装了 Inno Setup，再生成安装包

## GitHub 自动生成 EXE

把项目推到 GitHub 后：

1. Actions → `Build Windows EXE`
2. `Run workflow`
3. 下载 Artifact：`XiaozhiDesktopAssistant-Windows`

打 tag `v*` 也会触发构建。

## 商业发布前必须再做的事情

这份工程把功能都接起来了，但“能构建”不等于“未经测试即可直接卖”。发布前至少要完成：

- 在 Windows 10/11 真机验证 EXE 启动、DPAPI、托盘、自启
- 用你准备支持的每一家 API 各测一次工具调用
- 微信固定版本回归测试
- Chrome/Edge 不同版本回归测试
- 大 Excel / 大 PDF 压力测试
- Windows Defender/常用安全软件误报测试
- 给 EXE/安装包做代码签名
- 自动更新服务器和签名/哈希策略
- 收集最终构建依赖的完整许可证清单
- 隐私政策：明确哪些内容会发送给用户自己配置的 AI API
- 删除/发送/上传/命令等高风险动作最好再加“本地弹窗确认”，不要只依赖模型遵守工具描述

## 许可

项目包含/参考 `qaqbuyan/xiaozhi-mcp-computer` 的 MIT 商业友好许可，其 MIT 文本保留在：

`LICENSE-UPSTREAM-XIAOZHI-MCP-COMPUTER.txt`

具体第三方说明见 `THIRD_PARTY_NOTICES.md`。商业发布前请对实际锁定版本做完整许可证审查。
