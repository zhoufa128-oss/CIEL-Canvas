on run
    set appPath to POSIX path of (path to me)
    set shellScript to quoted form of (appPath & "Contents/Resources/install-ciel-update.sh")
    try
        set resultText to do shell script shellScript
        if resultText contains "FINAL_RESULT=SUCCESS" then
            display dialog "CIEL Canvas 更新安装成功。用户数据保持在原位置。" buttons {"好"} default button "好" with icon note
        else
            display dialog "CIEL Canvas 更新未完成：" & return & resultText buttons {"好"} default button "好" with icon caution
        end if
    on error errorText number errorNumber
        display dialog "CIEL Canvas 更新失败，安装器已尝试安全回滚。" & return & "错误：" & errorText & return & "代码：" & errorNumber buttons {"好"} default button "好" with icon stop
    end try
end run
