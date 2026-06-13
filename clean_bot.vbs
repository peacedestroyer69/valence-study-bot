Set fso = CreateObject("Scripting.FileSystemObject")
src = "C:\Users\ROG\Documents\antigravity\serene-mendeleev\bot.py"
tmp = "C:\Users\ROG\Documents\antigravity\serene-mendeleev\bot_tmp.py"

' Read as system default (ANSI/UTF-8 compatible for ASCII text)
Set f = fso.OpenTextFile(src, 1, False, 0)  ' ForReading=1, ASCII/ANSI=0
content = f.ReadAll
f.Close

cutMarker = "    bot.run(os.getenv(""BOT_TOKEN""))"

pos = InStr(1, content, cutMarker)
If pos > 0 Then
    keepLen = pos + Len(cutMarker)
    clean = Left(content, keepLen) & Chr(10)
    
    ' Write to temp file (ANSI mode)
    Set out = fso.CreateTextFile(tmp, True, False)  ' Overwrite=True, Unicode=False
    out.Write clean
    out.Close
    
    fso.CopyFile tmp, src, True
    fso.DeleteFile tmp
    
    WScript.Echo "SUCCESS: pos=" & pos & " keepLen=" & keepLen
Else
    WScript.Echo "ERROR: Marker not found. Content length=" & Len(content) & " first200=" & Left(content, 200)
End If
