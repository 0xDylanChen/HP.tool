@ECHO OFF
CD /D "%~dp0"
python "gui_main.py" %*
IF %ERRORLEVEL% NEQ 0 (
    ECHO Error launching HP AutoKit GUI.
    PAUSE
)