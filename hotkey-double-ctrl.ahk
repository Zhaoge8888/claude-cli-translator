#Requires AutoHotkey v2.0
#SingleInstance Force
Persistent

requestDir := EnvGet("LOCALAPPDATA") "\ClaudeCliTranslator\requests"
DirCreate(requestDir)
logFile := EnvGet("LOCALAPPDATA") "\ClaudeCliTranslator\hotkey.log"

lastCtrlTap := 0
isSending := false

Log("started")
ShowTip("Translator hotkey active: double Ctrl")

~LControl Up::HandleCtrlTap()
~RControl Up::HandleCtrlTap()

HandleCtrlTap() {
    global lastCtrlTap, isSending
    if isSending {
        return
    }

    now := A_TickCount
    if (now - lastCtrlTap <= 380) {
        lastCtrlTap := 0
        Log("double Ctrl detected")
        TriggerTranslate()
    } else {
        lastCtrlTap := now
    }
}

TriggerTranslate() {
    global requestDir, isSending
    isSending := true
    try {
        savedClipboard := ClipboardAll()
        A_Clipboard := ""

        Send "^+c"
        if !ClipWait(0.8) {
            A_Clipboard := savedClipboard
            Log("copy failed")
            ShowTip("没有复制到选中文本")
            return
        }

        text := Trim(A_Clipboard, "`r`n`t ")
        A_Clipboard := savedClipboard

        if (StrLen(text) < 2) {
            Log("empty selection")
            ShowTip("选中文本为空")
            return
        }

        fileName := requestDir "\request_" A_Now "_" A_TickCount "_" Random(1000, 9999) ".txt"
        FileAppend(text, fileName, "UTF-8")
        Log("sent " StrLen(text) " chars to " fileName)
        ShowTip("已发送到翻译分屏")
    } catch as err {
        Log("error: " err.Message)
        ShowTip("发送失败: " err.Message)
    } finally {
        isSending := false
    }
}

ShowTip(message) {
    ToolTip(message)
    SetTimer(() => ToolTip(), -900)
}

Log(message) {
    global logFile
    FileAppend(A_Now " " message "`n", logFile, "UTF-8")
}
