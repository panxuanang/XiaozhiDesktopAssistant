from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from .config import load_settings
from .logging_setup import setup_logging
from .agent import desktop_agent
from .tools import browser, files, office, pdf_tools, screen, system, wechat, windows

setup_logging()
logger = logging.getLogger(__name__)
settings = load_settings()
mcp = FastMCP("小智电脑助手")

mcp.tool(description="统一电脑智能体入口。把用户的完整任务交给客户端配置的 OpenAI/DeepSeek/豆包 API，由本地 Agent 自主调用文件、Office、网页、UIA 等工具完成。优先使用本工具以减少对小智后台模型的依赖。")(desktop_agent)


def _enabled(name: str) -> bool:
    return bool(getattr(settings.modules, name, True))


if _enabled("files"):
    mcp.tool(description="按名称在电脑目录中搜索文件或文件夹。root 可写桌面、下载、文档或具体路径。") (files.search_files)
    mcp.tool(description="查看一个目录中的文件和子目录。") (files.list_directory)
    mcp.tool(description="创建 UTF-8 文本文件。Word 文档请使用 create_word_document/write_material。") (files.create_text_file)
    mcp.tool(description="移动文件或文件夹。") (files.move_path)
    mcp.tool(description="复制文件或文件夹。") (files.copy_path)
    mcp.tool(description="删除文件或文件夹。首次必须返回确认提示；只有用户明确确认后才能 confirmed=true。") (files.delete_path)
    mcp.tool(description="按扩展名整理目录。必须先向用户确认。") (files.organize_by_extension)

if _enabled("office"):
    mcp.tool(description="直接生成真正的 .docx Word 文件，不需要打开 Word 软件。") (office.create_word_document)
    mcp.tool(description="使用用户在客户端配置的 AI API 撰写材料并直接生成 Word。适合通知、总结、汇报、方案、纪要。") (office.write_material)
    mcp.tool(description="读取 Word 文档正文。") (office.read_word_document)
    mcp.tool(description="使用用户自己的 AI API 按要求修改 Word，并生成修改版。") (office.rewrite_word_document)
    mcp.tool(description="本地读取 Excel 并返回结构化统计摘要，不把整张表直接发给 AI。") (office.excel_profile)
    mcp.tool(description="本地分析 Excel 后，把统计摘要交给用户自己的 AI API 形成结论；可同时生成 Word 报告。") (office.analyze_excel)
    mcp.tool(description="读取 Excel 指定工作表的前若干行。") (office.excel_preview)

if _enabled("pdf"):
    mcp.tool(description="读取 PDF 的可提取文本。扫描 PDF 需要 OCR。") (pdf_tools.read_pdf)
    mcp.tool(description="用用户自己的 AI API 总结 PDF 或回答关于 PDF 的问题。") (pdf_tools.summarize_pdf)
    mcp.tool(description="在 PDF 文本中搜索关键词并返回上下文。") (pdf_tools.search_pdf)
    mcp.tool(description="对扫描版 PDF 逐页渲染并使用本地 OCR 提取文字。") (pdf_tools.ocr_scanned_pdf)
    mcp.tool(description="合并多个 PDF 为一个 PDF。") (pdf_tools.merge_pdfs)

if _enabled("browser"):
    mcp.tool(description="打开网页。使用独立的小智浏览器配置目录，可登录网站并保留登录状态。") (browser.browser_open)
    mcp.tool(description="在 Bing/百度/Google 中搜索网页。") (browser.browser_search)
    mcp.tool(description="读取当前网页标题、URL 和正文 DOM 文本，不依赖 OCR。") (browser.browser_current_page)
    mcp.tool(description="用用户自己的 AI API 总结当前网页或回答网页问题。") (browser.summarize_current_webpage)
    mcp.tool(description="按网页上的可见文字点击按钮或链接，优先 DOM，不走坐标。") (browser.browser_click_text)
    mcp.tool(description="按字段的标签/占位符/name 填写网页输入框。") (browser.browser_fill)
    mcp.tool(description="提取当前网页中的 HTML 表格。") (browser.browser_extract_tables)
    mcp.tool(description="把本机文件设置到网页文件上传控件，使用 DevTools 而不是模拟点击文件选择框。") (browser.browser_upload_file)
    mcp.tool(description="点击指定文字并允许浏览器把文件下载到给定目录。") (browser.browser_download_by_text)

if _enabled("windows"):
    mcp.tool(description="列出当前可见 Windows 窗口标题。") (windows.list_windows)
    mcp.tool(description="激活包含指定标题的窗口。") (windows.activate_window)
    mcp.tool(description="最小化、最大化、恢复或关闭指定窗口。") (windows.window_action)
    mcp.tool(description="移动并缩放指定窗口。") (windows.move_resize_window)
    mcp.tool(description="读取指定窗口的 Windows UI Automation 控件树；比 OCR 更稳定。") (windows.ui_tree)
    mcp.tool(description="通过 Windows UI Automation 按控件名称点击，不依赖屏幕坐标。") (windows.ui_click)
    mcp.tool(description="启动程序、快捷方式或系统可识别的应用。") (windows.open_program)

if _enabled("wechat"):
    mcp.tool(description="准备一条个人微信消息但不发送。必须先调用本工具，并把预览内容读给用户确认。") (wechat.prepare_wechat_message)
    mcp.tool(description="准备向微信联系人发送文件但不立即发送，必须先向用户确认。") (wechat.prepare_wechat_file)
    mcp.tool(description="只有用户明确确认上一条微信后才可调用。根据 pending_id 搜索联系人并发送。") (wechat.wechat_confirm_send)
    mcp.tool(description="读取当前微信窗口 UIA 可访问的文字，用于辅助判断当前聊天内容；不同微信版本效果可能不同。") (wechat.read_wechat_ui)

if _enabled("ocr"):
    mcp.tool(description="本地截屏 OCR，可按关键词过滤并返回文字中心坐标。仅在 UIA/DOM 不能操作时兜底使用。") (screen.local_ocr_screen)

if _enabled("screen"):
    mcp.tool(description="截取当前全部屏幕并保存为 PNG。") (screen.take_screenshot)
    mcp.tool(description="把当前屏幕截图交给用户配置的视觉模型分析；模型必须支持图像输入。") (screen.analyze_screen)

if _enabled("system"):
    mcp.tool(description="获取 CPU、内存和磁盘状态。") (system.system_status)
    mcp.tool(description="设置 Windows 系统主音量。") (system.set_system_volume)
    mcp.tool(description="执行系统命令。危险操作，必须用户明确确认后 confirmed=true。") (system.run_command)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
