#!/usr/bin/env python3
import ctypes
import datetime as _dt
import os
import queue
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path


APP_NAME = "ClaudeCliTranslator"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME
REQUEST_DIR = STATE_DIR / "requests"
LOG_FILE = STATE_DIR / "hotkey.log"

DOUBLE_TAP_MS = 380
COPY_STABILIZE_DELAY_SECONDS = 0.12
COPY_ATTEMPT_WAIT_SECONDS = 0.75

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_HOTKEY = 0x0312
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_SPACE = 0x20
VK_C = 0x43
VK_INSERT = 0x2D
KEYEVENTF_KEYUP = 0x0002
INPUT_KEYBOARD = 1
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
ERROR_ALREADY_EXISTS = 183
MOD_CONTROL = 0x0002
HOTKEY_ID_CTRL_SPACE = 1001

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
ULONG_PTR = ctypes.c_size_t


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUT_UNION)]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
user32.CallNextHookEx.restype = ctypes.c_long
user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
user32.GetMessageW.restype = wintypes.BOOL
user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, wintypes.DWORD, ULONG_PTR]
user32.keybd_event.restype = None
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.OpenClipboard.restype = wintypes.BOOL
user32.CloseClipboard.argtypes = []
user32.CloseClipboard.restype = wintypes.BOOL
user32.EmptyClipboard.argtypes = []
user32.EmptyClipboard.restype = wintypes.BOOL
user32.GetClipboardData.argtypes = [wintypes.UINT]
user32.GetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.SetClipboardData.restype = wintypes.HANDLE

kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
kernel32.GetLastError.restype = wintypes.DWORD
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.restype = wintypes.BOOL


last_ctrl_tap = 0.0
is_sending = False
hook_handle = None
trigger_queue: "queue.Queue[str]" = queue.Queue()


def log(message: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"{stamp} {message}\n")


def enqueue_trigger(source: str) -> None:
    if is_sending:
        log(f"{source} ignored: copy already in progress")
        return
    if not trigger_queue.empty():
        log(f"{source} ignored: trigger already queued")
        return
    trigger_queue.put(source)


def is_key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def wait_for_hotkey_release(timeout_seconds: float = 0.7) -> None:
    deadline = time.time() + timeout_seconds
    watched = (VK_CONTROL, VK_LCONTROL, VK_RCONTROL, VK_SPACE)
    while time.time() < deadline:
        if not any(is_key_down(vk) for vk in watched):
            return
        time.sleep(0.02)


def open_clipboard() -> bool:
    deadline = time.time() + 0.6
    while time.time() < deadline:
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.03)
    return False


def get_clipboard_text() -> str:
    if not open_clipboard():
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> None:
    if not open_clipboard():
        return
    try:
        user32.EmptyClipboard()
        data = text + "\0"
        size = len(data.encode("utf-16-le"))
        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            return
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return
        try:
            ctypes.memmove(pointer, data.encode("utf-16-le"), size)
        finally:
            kernel32.GlobalUnlock(handle)
        user32.SetClipboardData(CF_UNICODETEXT, handle)
    finally:
        user32.CloseClipboard()


def key_input(vk: int, flags: int = 0) -> INPUT:
    item = INPUT()
    item.type = INPUT_KEYBOARD
    item.union.ki = KEYBDINPUT(vk, 0, flags, 0, 0)
    return item


def send_key_chord(name: str, keys: list[int]) -> None:
    cb_size = ctypes.sizeof(INPUT)
    events = [key_input(vk) for vk in keys]
    events.extend(key_input(vk, KEYEVENTF_KEYUP) for vk in reversed(keys))
    inputs = (INPUT * len(events))(*events)
    sent = user32.SendInput(len(events), inputs, cb_size)
    if sent == len(events):
        return

    error = ctypes.get_last_error()
    log(f"{name}: SendInput sent {sent}/{len(events)} events, error={error}, cbSize={cb_size}; falling back to keybd_event")
    for event in events:
        vk = event.union.ki.wVk
        flags = event.union.ki.dwFlags
        user32.keybd_event(vk, 0, flags, 0)
        time.sleep(0.015)


def wait_for_copied_text(sentinel: str, timeout_seconds: float) -> str:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        current = get_clipboard_text()
        if current and current != sentinel:
            return current.strip("\r\n\t ")
        time.sleep(0.04)
    return ""


def copy_selected_text(sentinel: str) -> str:
    attempts = (
        ("Ctrl+Shift+C", [VK_CONTROL, VK_SHIFT, VK_C]),
        ("Ctrl+Insert", [VK_CONTROL, VK_INSERT]),
    )
    for name, keys in attempts:
        log(f"copy attempt: {name}")
        send_key_chord(name, keys)
        time.sleep(0.05)
        copied = wait_for_copied_text(sentinel, COPY_ATTEMPT_WAIT_SECONDS)
        if copied:
            log(f"{name} copied {len(copied)} chars")
            return copied
        log(f"{name} copied no text")
    return ""


def write_request(text: str) -> Path:
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = REQUEST_DIR / f"request_{stamp}_{os.getpid()}.txt"
    path.write_text(text, encoding="utf-8")
    return path


def trigger_translate(source: str) -> None:
    global is_sending
    if is_sending:
        return
    is_sending = True
    try:
        log(f"{source} trigger detected")
        wait_for_hotkey_release()
        saved_text = get_clipboard_text()
        sentinel = f"__CLAUDE_CLI_TRANSLATOR_SENTINEL_{time.time_ns()}__"
        set_clipboard_text(sentinel)
        time.sleep(COPY_STABILIZE_DELAY_SECONDS)
        copied = copy_selected_text(sentinel)

        set_clipboard_text(saved_text)

        if len(copied) < 2:
            log("copy failed or selection empty")
            return

        path = write_request(copied)
        log(f"sent {len(copied)} chars to {path}")
    except Exception as exc:
        log(f"error: {exc}")
    finally:
        is_sending = False


def trigger_worker() -> None:
    while True:
        source = trigger_queue.get()
        try:
            trigger_translate(source)
        finally:
            trigger_queue.task_done()


def keyboard_proc(n_code, w_param, l_param):
    global last_ctrl_tap
    if n_code == 0 and not is_sending:
        event = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
        if w_param in (WM_KEYUP, WM_SYSKEYUP) and event.vkCode in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
            now = time.monotonic() * 1000
            if now - last_ctrl_tap <= DOUBLE_TAP_MS:
                last_ctrl_tap = 0.0
                enqueue_trigger("double Ctrl")
            else:
                last_ctrl_tap = now
    return user32.CallNextHookEx(hook_handle, n_code, w_param, l_param)


def ensure_single_instance() -> None:
    mutex = kernel32.CreateMutexW(None, True, "ClaudeCliTranslatorDoubleCtrlHotkey")
    if not mutex:
        return
    if kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        log("already running")
        sys.exit(0)


def main() -> int:
    global hook_handle
    if os.name != "nt":
        print("This hotkey helper only supports Windows.", file=sys.stderr)
        return 1
    ensure_single_instance()
    REQUEST_DIR.mkdir(parents=True, exist_ok=True)
    log("python hotkey started")
    worker = threading.Thread(target=trigger_worker, name="trigger-worker", daemon=True)
    worker.start()
    ctrl_space_registered = bool(user32.RegisterHotKey(None, HOTKEY_ID_CTRL_SPACE, MOD_CONTROL, VK_SPACE))
    if ctrl_space_registered:
        log("Ctrl+Space registered")
    else:
        log(f"Ctrl+Space registration failed: {ctypes.get_last_error()}")
    print("Claude CLI Translator hotkey active: Ctrl+Space, fallback double Ctrl")
    print(f"Log: {LOG_FILE}")
    callback = HOOKPROC(keyboard_proc)
    hook_handle = user32.SetWindowsHookExW(WH_KEYBOARD_LL, callback, kernel32.GetModuleHandleW(None), 0)
    if not hook_handle:
        error = ctypes.get_last_error()
        log(f"SetWindowsHookEx failed: {error}")
        print(f"Failed to install keyboard hook: {error}", file=sys.stderr)
        return 1
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID_CTRL_SPACE:
            enqueue_trigger("Ctrl+Space")
            continue
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
    if ctrl_space_registered:
        user32.UnregisterHotKey(None, HOTKEY_ID_CTRL_SPACE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
