Set fso = CreateObject("Scripting.FileSystemObject")
file1 = "C:\Users\ROG\Documents\app.lock"
file2 = "C:\Users\ROG\Documents\ComfyUI\.venv\.lock"

On Error Resume Next

If fso.FileExists(file1) Then
    fso.DeleteFile file1, True
    If Err.Number <> 0 Then
        WScript.Echo "Failed to delete file1: " & Err.Description
        Err.Clear
    Else
        WScript.Echo "Successfully deleted file1"
    End If
Else
    WScript.Echo "file1 does not exist"
End If

If fso.FileExists(file2) Then
    fso.DeleteFile file2, True
    If Err.Number <> 0 Then
        WScript.Echo "Failed to delete file2: " & Err.Description
        Err.Clear
    Else
        WScript.Echo "Successfully deleted file2"
    End If
Else
    WScript.Echo "file2 does not exist"
End If
