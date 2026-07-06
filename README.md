# Claude CLI Translator

一个不修改 Claude Code 本体文件的 Windows 分屏翻译助手。

> 非 Anthropic 官方项目。它不会修改 Claude Code 安装文件，只翻译你手动框选的终端文本。

## 工作方式

- 左侧 Windows Terminal pane 运行 `claude`
- 右侧 pane 运行 `translator-pane.py`
- 在左侧框选英文后，双击 `Ctrl`
- Python 热键程序把选区发送到本地请求目录
- 右侧翻译 pane 调用 DeepSeek/OpenAI 兼容 API，并以紧凑模式显示中文

## 文件

- `translator-pane.py`：常驻翻译 CLI
- `hotkey-double-ctrl.py`：Windows 双击 Ctrl 热键
- `hotkey-double-ctrl.ahk`：AutoHotkey v2 备用热键
- `start-claude-translator.ps1`：一键启动热键、Claude Code 和翻译分屏
- `launch-split.ps1`：启动左右分屏
- `run-translator.ps1`：启动翻译 pane
- `send-clipboard.ps1`：把剪贴板内容发送给翻译 pane
- `send-selection.ps1`：手动复制选区并发送给翻译 pane
- `config.example.json`：配置模板
- `glossary.json`：Claude Code 术语表

## 依赖

- Windows Terminal
- Python 3.9+。如果在 Codex Desktop 里运行，`run-translator.ps1` 会尝试使用 Codex 自带 Python。
- 双击 Ctrl 热键默认使用 `hotkey-double-ctrl.py`，不需要 AutoHotkey。`hotkey-double-ctrl.ahk` 只是备用方案。
- 一个 OpenAI Chat Completions 兼容 API，例如 DeepSeek

## 首次配置

复制配置文件：

```powershell
Copy-Item .\config.example.json .\config.json
```

设置 API Key：

```powershell
setx DEEPSEEK_API_KEY "你的 API Key"
```

不要把真实 API Key 写入仓库。`config.json` 已被 `.gitignore` 忽略。

默认配置使用 DeepSeek 官方当前的 `deepseek-v4-pro`：

```json
{
  "base_url": "https://api.deepseek.com",
  "model": "deepseek-v4-pro",
  "extra_body": {
    "thinking": {
      "type": "disabled"
    }
  }
}
```

纯翻译任务默认关闭 thinking mode，通常更快、更稳定。如果你想使用最强推理模式，可以把 `extra_body` 改为：

```json
{
  "thinking": {
    "type": "enabled",
    "reasoning_effort": "max"
  }
}
```

## 启动

推荐一键启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-claude-translator.ps1
```

安装桌面和开始菜单快捷方式：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-shortcut.ps1
```

如果系统不允许脚本自动固定到任务栏，可以在开始菜单搜索 `Claude Code Translator`，右键选择固定到任务栏。

这会自动启动双击 Ctrl 热键、Claude Code 和翻译分屏。默认下方翻译 pane 占 32% 高度。

调整初始高度：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-claude-translator.ps1 -TranslatorSize 0.25
```

左右分屏：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-claude-translator.ps1 -SideBySide
```

手动调整 Windows Terminal 分屏大小：

```text
Alt+Shift+↑ / Alt+Shift+↓
```

手动分步启动：

1. 运行热键脚本：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-hotkey.ps1
```

2. 启动分屏：

```powershell
powershell -ExecutionPolicy Bypass -File .\launch-split.ps1
```

3. 在 Claude Code 左侧 pane 框选英文，双击 `Ctrl`。

## 诊断与测试

检查热键进程：

```powershell
powershell -ExecutionPolicy Bypass -File .\diagnose-hotkey.ps1
```

停止热键进程：

```powershell
powershell -ExecutionPolicy Bypass -File .\stop-hotkey.ps1
```

如果热键复制不稳定，可以先手动 `Ctrl+Shift+C` 复制选区，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\send-clipboard.ps1
```

## 离线验证

不调用 API，只测试清理、队列、术语命中和显示格式：

```powershell
powershell -ExecutionPolicy Bypass -Command "$py='$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'; if(Test-Path $py){& $py .\translator-pane.py --once .\sample-input.txt --dry-run}else{python .\translator-pane.py --once .\sample-input.txt --dry-run}"
```

## 隐私说明

选中的 Claude Code 输出会发送给你配置的 API 服务。不要选中包含密钥、私有源码、客户数据或敏感路径的内容，除非你确认该 API 使用方式符合你的安全要求。

## 已知限制

- 不读取 Claude Code 屏幕，只翻译你框选的文本。
- 终端颜色、光标位置、动态 TUI 状态不会保留。
- 翻译质量取决于模型和术语表。
- 双击 Ctrl 是全局热键，目前不限制只在 Windows Terminal 中生效。
