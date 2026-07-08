#!/usr/bin/env python3
import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


APP_NAME = "ClaudeCliTranslator"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(SCRIPT_DIR))) / APP_NAME
DEFAULT_REQUEST_DIR = DEFAULT_STATE_DIR / "requests"
DEFAULT_CACHE_FILE = DEFAULT_STATE_DIR / "cache.json"


DEFAULT_CONFIG = {
    "api_key_env": "DEEPSEEK_API_KEY",
    "api_key": "",
    "base_url": "https://api.deepseek.com",
    "model": "deepseek-v4-pro",
    "temperature": 0.1,
    "timeout_seconds": 60,
    "extra_body": {"thinking": {"type": "disabled"}},
    "target_language": "zh-CN",
    "max_chars": 6000,
    "compact_mode": True,
    "clean_visual_selection": True,
    "interleave_line_pairs": True,
    "request_dir": str(DEFAULT_REQUEST_DIR),
    "cache_file": str(DEFAULT_CACHE_FILE),
    "glossary_file": "glossary.json",
    "show_original": True,
    "show_glossary_hits": False,
}


ANSI_RE = re.compile(
    r"""
    \x1B
    (?:
        \[[0-?]*[ -/]*[@-~]      # CSI
      | \][^\x07]*(?:\x07|\x1B\\) # OSC
      | [PX^_].*?\x1B\\          # DCS/PM/APC
      | [@-Z\\-_]                # 2-byte sequence
    )
    """,
    re.VERBOSE | re.DOTALL,
)

CONTROL_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
TEXT_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
WIDE_SPACE_RE = re.compile(r"\s{3,}")


def is_terminal_decoration_char(char: str) -> bool:
    code = ord(char)
    return (
        0x2500 <= code <= 0x257F  # Box Drawing
        or 0x2580 <= code <= 0x259F  # Block Elements
        or 0x2800 <= code <= 0x28FF  # Braille Patterns
    )


def has_terminal_decoration(line: str) -> bool:
    return any(is_terminal_decoration_char(char) for char in line)


def strip_visual_edges(text: str) -> str:
    chars = list(text.strip())
    while chars and (chars[0].isspace() or chars[0] in "|¦" or is_terminal_decoration_char(chars[0])):
        chars.pop(0)
    while chars and (chars[-1].isspace() or chars[-1] in "|¦" or is_terminal_decoration_char(chars[-1])):
        chars.pop()
    return "".join(chars).strip()


def is_meaningful_text(segment: str) -> bool:
    if not segment:
        return False
    without_decoration = "".join(char for char in segment if not is_terminal_decoration_char(char)).strip()
    if not without_decoration:
        return False
    return bool(TEXT_RE.search(without_decoration)) or without_decoration.startswith(("/", "--"))


def split_visual_line(line: str) -> list[str]:
    normalized_chars = []
    saw_visual_separator = False

    for char in line:
        if is_terminal_decoration_char(char):
            normalized_chars.append(" ")
            saw_visual_separator = True
        elif char in "|¦":
            normalized_chars.append("\t")
            saw_visual_separator = True
        else:
            normalized_chars.append(char)

    normalized = "".join(normalized_chars)
    if saw_visual_separator or WIDE_SPACE_RE.search(normalized):
        raw_parts = re.split(r"\t+|\s{3,}", normalized)
    else:
        raw_parts = [normalized]

    parts = []
    for part in raw_parts:
        cleaned = strip_visual_edges(part)
        if is_meaningful_text(cleaned):
            parts.append(cleaned)
    return parts


def clean_visual_selection_lines(lines: list[str]) -> list[str]:
    cleaned_lines = []
    last_blank = False

    for line in lines:
        if not line.strip():
            if cleaned_lines and not last_blank:
                cleaned_lines.append("")
                last_blank = True
            continue

        needs_visual_cleanup = (
            has_terminal_decoration(line)
            or "|" in line
            or "¦" in line
            or bool(WIDE_SPACE_RE.search(line))
        )
        parts = split_visual_line(line) if needs_visual_cleanup else [line.rstrip()]

        if not parts:
            continue

        for part in parts:
            if cleaned_lines and cleaned_lines[-1] == part:
                continue
            cleaned_lines.append(part)
            last_blank = False

    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)
    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()
    return cleaned_lines


def expand_path(value: str) -> Path:
    value = os.path.expandvars(value)
    return Path(value).expanduser()


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_config(path: Path) -> dict:
    config = DEFAULT_CONFIG.copy()
    if path.exists():
        user_config = load_json(path, {})
        if not isinstance(user_config, dict):
            raise ValueError(f"Config must be a JSON object: {path}")
        config.update(user_config)
    return config


def load_glossary(path_value: str) -> dict:
    path = expand_path(path_value)
    if not path.is_absolute():
        path = SCRIPT_DIR / path
    glossary = load_json(path, {})
    if not isinstance(glossary, dict):
        raise ValueError(f"Glossary must be a JSON object: {path}")
    return {str(k): str(v) for k, v in glossary.items()}


def load_cache(cache_path: Path) -> dict:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        return {}
    try:
        data = load_json(cache_path, {})
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(cache_path: Path, cache: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    tmp.replace(cache_path)


def clean_terminal_text(text: str, visual_cleanup: bool = True) -> str:
    text = ANSI_RE.sub("", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x08", "")
    text = CONTROL_RE.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    if visual_cleanup:
        lines = clean_visual_selection_lines(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0 or len(text) <= max_chars:
        return text, False
    return text[:max_chars].rstrip() + "\n[...truncated...]", True


def glossary_hits(text: str, glossary: dict, limit: int = 80) -> list[tuple[str, str]]:
    lower = text.lower()
    hits = []
    for source, target in glossary.items():
        if not source:
            continue
        if source.startswith("/") or source.startswith("--"):
            found = source in text
        else:
            found = source.lower() in lower
        if found:
            hits.append((source, target))
            if len(hits) >= limit:
                break
    return hits


def glossary_prompt(glossary: dict, hits: list[tuple[str, str]]) -> str:
    if hits:
        selected = hits
    else:
        important = [
            "Claude Code",
            "permission",
            "Allow once",
            "Allow always",
            "Deny",
            "tool use",
            "Bash",
            "Read",
            "Write",
            "Edit",
            "MCP",
            "hook",
            "subagent",
            "slash command",
            "Plan mode",
            "/help",
            "/config",
            "/permissions",
        ]
        selected = [(k, glossary[k]) for k in important if k in glossary]
    return "\n".join(f"- {source} => {target}" for source, target in selected[:120])


def cache_key(text: str, config: dict, glossary: dict) -> str:
    payload = {
        "text": text,
        "base_url": config.get("base_url", ""),
        "model": config.get("model", ""),
        "extra_body": config.get("extra_body", {}),
        "target_language": config.get("target_language", ""),
        "glossary_hash": hashlib.sha256(
            json.dumps(glossary, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def api_key(config: dict) -> str:
    direct = str(config.get("api_key") or "").strip()
    if direct:
        return direct
    env_name = str(config.get("api_key_env") or "DEEPSEEK_API_KEY")
    return os.environ.get(env_name, "").strip()


def translate_with_chat_api(text: str, config: dict, glossary: dict, hits: list[tuple[str, str]]) -> str:
    key = api_key(config)
    if not key:
        raise RuntimeError(
            f"Missing API key. Set {config.get('api_key_env', 'DEEPSEEK_API_KEY')} or put api_key in config.json."
        )

    base_url = str(config.get("base_url", "")).rstrip("/")
    if not base_url:
        raise RuntimeError("Missing base_url in config.")
    url = f"{base_url}/chat/completions"

    system_prompt = f"""你是一个专门翻译 Claude Code CLI/TUI 文案的翻译器。
目标：把英文命令行界面文字翻译成简体中文，适合在旁边的翻译 CLI 中紧凑显示。

严格规则：
1. 只输出中文译文，不要解释，不要加前后缀。
2. 保留原有换行、缩进、列表结构和表格的大致布局。
3. 不翻译命令、斜杠命令、flag、快捷键、文件路径、URL、环境变量、JSON/YAML/TOML 字段名、代码标识符。
4. 安全/权限相关文字要直译清楚，不能弱化风险。
5. Claude Code、MCP、Bash、API Key、token 等专有名词按术语表处理。
6. 如果原文已经是中文，原样返回。

术语表：
{glossary_prompt(glossary, hits)}
"""

    payload = {
        "model": config.get("model", "deepseek-v4-pro"),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
        "temperature": float(config.get("temperature", 0.1)),
        "stream": False,
    }
    extra_body = config.get("extra_body")
    if isinstance(extra_body, dict):
        payload.update(extra_body)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
        },
        method="POST",
    )
    timeout = int(config.get("timeout_seconds", 60))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {detail}") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Unexpected API response: {json.dumps(data, ensure_ascii=False)[:1000]}") from e


def dry_run_translate(text: str, hits: list[tuple[str, str]]) -> str:
    result = text
    for source, target in sorted(hits, key=lambda item: len(item[0]), reverse=True):
        if source.startswith("/") or source.startswith("--"):
            continue
        result = re.sub(re.escape(source), target, result, flags=re.IGNORECASE)
    return "[离线演示] " + result


def nonblank_lines(text: str) -> list[str]:
    return [line.rstrip() for line in text.splitlines() if line.strip()]


def can_interleave_line_pairs(original: str, translated: str, config: dict) -> bool:
    if not config.get("interleave_line_pairs", True):
        return False
    original_lines = nonblank_lines(original)
    translated_lines = nonblank_lines(translated)
    if not original_lines or len(original_lines) != len(translated_lines):
        return False
    if len(original_lines) > 16:
        return False
    if any(len(line) > 160 for line in original_lines + translated_lines):
        return False
    if "```" in original or "```" in translated:
        return False
    return True


def print_interleaved_line_pairs(original: str, translated: str) -> None:
    for source, target in zip(nonblank_lines(original), nonblank_lines(translated)):
        print("EN | " + source)
        print("ZH | " + target)


def print_compact(original: str, translated: str, hits: list[tuple[str, str]], config: dict, cached: bool = False) -> None:
    timestamp = _dt.datetime.now().strftime("%H:%M:%S")
    tag = "缓存" if cached else "翻译"
    print(f"\n[{timestamp}] {tag}")
    if config.get("show_original", True) and can_interleave_line_pairs(original, translated, config):
        print_interleaved_line_pairs(original, translated)
    elif config.get("show_original", True):
        print("EN | " + original.replace("\n", "\nEN | "))
        print("ZH | " + translated.replace("\n", "\nZH | "))
    else:
        print("ZH | " + translated.replace("\n", "\nZH | "))
    if config.get("show_glossary_hits", False) and hits:
        compact_hits = ", ".join(f"{src}->{dst}" for src, dst in hits[:12])
        print("术语 | " + compact_hits)
    sys.stdout.flush()


def translate_text(text: str, config: dict, glossary: dict, dry_run: bool = False) -> tuple[str, bool, list[tuple[str, str]]]:
    cleaned = clean_terminal_text(text, bool(config.get("clean_visual_selection", True)))
    max_chars = int(config.get("max_chars", 6000))
    cleaned, truncated = truncate_text(cleaned, max_chars)
    if not cleaned:
        return "", False, []
    hits = glossary_hits(cleaned, glossary)

    if dry_run:
        translated = dry_run_translate(cleaned, hits)
        if truncated:
            translated += "\n[原文过长，已截断后翻译]"
        return translated, False, hits

    cache_path = expand_path(str(config.get("cache_file") or DEFAULT_CACHE_FILE))
    cache = load_cache(cache_path)
    key = cache_key(cleaned, config, glossary)
    if key in cache:
        return cache[key], True, hits

    translated = translate_with_chat_api(cleaned, config, glossary, hits)
    if truncated:
        translated += "\n[原文过长，已截断后翻译]"
    cache[key] = translated
    save_cache(cache_path, cache)
    return translated, False, hits


def process_once(path: Path, config: dict, glossary: dict, dry_run: bool) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_terminal_text(text, bool(config.get("clean_visual_selection", True)))
    translated, cached, hits = translate_text(text, config, glossary, dry_run=dry_run)
    if not translated:
        print("No text to translate.")
        return 1
    print_compact(cleaned, translated, hits, config, cached=cached)
    return 0


def watch_requests(config: dict, glossary: dict, dry_run: bool) -> None:
    request_dir = expand_path(str(config.get("request_dir") or DEFAULT_REQUEST_DIR))
    request_dir.mkdir(parents=True, exist_ok=True)
    print("Claude CLI Translator MVP")
    print(f"监听目录: {request_dir}")
    print("在 Claude Code 中框选英文后按 Ctrl+Space；双击 Ctrl 备用。按 Ctrl+C 退出翻译 pane。")
    print("调整分屏大小: Alt+Shift+↑/↓；切换分屏焦点: Alt+↑/↓。")
    sys.stdout.flush()

    while True:
        files = sorted(request_dir.glob("request_*.txt"))
        if not files:
            time.sleep(0.25)
            continue
        for path in files:
            processing_path = path.with_suffix(".processing")
            try:
                path.rename(processing_path)
            except FileNotFoundError:
                continue
            except PermissionError:
                time.sleep(0.1)
                continue
            try:
                text = processing_path.read_text(encoding="utf-8", errors="replace")
                cleaned = clean_terminal_text(text, bool(config.get("clean_visual_selection", True)))
                if cleaned:
                    translated, cached, hits = translate_text(text, config, glossary, dry_run=dry_run)
                    print_compact(cleaned, translated, hits, config, cached=cached)
            except Exception as e:
                print(f"\n[错误] {e}", file=sys.stderr)
                sys.stderr.flush()
            finally:
                try:
                    processing_path.unlink()
                except FileNotFoundError:
                    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Claude Code CLI side-pane translator.")
    parser.add_argument("--config", default=str(SCRIPT_DIR / "config.json"), help="Path to config.json")
    parser.add_argument("--once", help="Translate one text file and exit")
    parser.add_argument("--dry-run", action="store_true", help="Do not call API; show offline glossary substitution demo")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser()
    if not config_path.exists() and config_path.name == "config.json":
        example = SCRIPT_DIR / "config.example.json"
        if example.exists():
            config_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
    config = load_config(config_path)
    glossary = load_glossary(str(config.get("glossary_file") or "glossary.json"))

    if args.once:
        return process_once(Path(args.once), config, glossary, dry_run=args.dry_run)
    watch_requests(config, glossary, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nBye.")
        raise SystemExit(0)
