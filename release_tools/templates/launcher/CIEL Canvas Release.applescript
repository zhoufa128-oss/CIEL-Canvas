use scripting additions

property launcherBuild : "2026.07.16.ciel-macos-arm64-launcher-rc1"

on appendLog(logFile, messageText)
    set stamp to do shell script "/bin/date '+%Y-%m-%d %H:%M:%S'"
    set logParent to do shell script "/usr/bin/dirname " & quoted form of logFile
    do shell script "/bin/mkdir -p " & quoted form of logParent
    do shell script "/bin/echo " & quoted form of (stamp & " " & messageText) & " >> " & quoted form of logFile
end appendLog

on extractFinalResult(outputText)
    set previousDelimiters to AppleScript's text item delimiters
    try
        set AppleScript's text item delimiters to "FINAL_RESULT="
        set resultParts to text items of outputText
        if (count of resultParts) is less than 2 then
            set AppleScript's text item delimiters to previousDelimiters
            return "UNKNOWN_RESULT"
        end if
        set resultTail to item -1 of resultParts
        set AppleScript's text item delimiters to linefeed
        set resultCode to text item 1 of resultTail
        set AppleScript's text item delimiters to previousDelimiters
        return resultCode
    on error
        set AppleScript's text item delimiters to previousDelimiters
        return "UNKNOWN_RESULT"
    end try
end extractFinalResult

on reasonForCode(resultCode)
    if resultCode is "PORT_OCCUPIED" then
        return "Port 3015 is already used by another program."
    else if resultCode is "VERSION_MISMATCH" then
        return "Another CIEL Canvas version is already running."
    else if resultCode is "PROCESS_EXITED" then
        return "The CIEL Canvas service exited during startup."
    else if resultCode is "HEALTH_TIMEOUT" then
        return "The CIEL Canvas service did not become ready in time."
    else if resultCode is "RELEASE_INCOMPLETE" then
        return "The release is incomplete or missing its runtime files."
    else if resultCode is "RELEASE_METADATA_INVALID" then
        return "The release metadata is invalid."
    else
        return "CIEL Canvas could not start (" & resultCode & ")."
    end if
end reasonForCode

on run
    set appPath to POSIX path of (path to me)
    if appPath ends with "/" then set appPath to text 1 thru -2 of appPath
    set installRoot to do shell script "/usr/bin/dirname " & quoted form of appPath
    set logDirectory to installRoot & "/UserData/logs"
    set logFile to logDirectory & "/ciel-canvas-launcher.log"
    set commandPath to installRoot & "/Application/current/bin/start-ciel-release.sh"
    my appendLog(logFile, "START LAUNCHER_BUILD=" & launcherBuild)

    if appPath contains "/AppTranslocation/" then
        my appendLog(logFile, "FINAL_RESULT=APP_TRANSLOCATED")
        display dialog "Move the complete CIEL Canvas folder out of the quarantined location, then open the app again." with title "CIEL Canvas" buttons {"OK"} default button "OK" with icon stop
        return
    end if

    set commandExists to do shell script "if [ -x " & quoted form of commandPath & " ]; then echo yes; else echo no; fi"
    if commandExists is not "yes" then
        my appendLog(logFile, "FINAL_RESULT=RELEASE_INCOMPLETE")
        display dialog "The release is incomplete: Application/current/bin/start-ciel-release.sh is missing." with title "CIEL Canvas" buttons {"OK"} default button "OK" with icon stop
        return
    end if

    try
        display notification "Starting CIEL Canvas..." with title "CIEL Canvas"
    end try
    try
        with timeout of 70 seconds
            set commandOutput to do shell script "/bin/zsh " & quoted form of commandPath & " 2>&1"
        end timeout
        my appendLog(logFile, commandOutput)
        set resultCode to my extractFinalResult(commandOutput)
        if resultCode is "SUCCESS" then return
        display dialog my reasonForCode(resultCode) & return & return & "See UserData/logs for details." with title "CIEL Canvas" buttons {"OK"} default button "OK" with icon stop
    on error errorMessage number errorNumber
        my appendLog(logFile, "APPLESCRIPT_ERROR_NUMBER=" & errorNumber & " APPLESCRIPT_ERROR_TEXT=" & errorMessage)
        display dialog "The CIEL Canvas launcher encountered an error. See UserData/logs for details." with title "CIEL Canvas" buttons {"OK"} default button "OK" with icon stop
    end try
end run
