@echo off
REM Run ONCE as Administrator. Makes .engine start with Windows, before anyone logs in.
schtasks /Create /TN ".engine" /TR "\"%~dp0start_engine.bat\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
echo.
echo Done. To remove it later:  schtasks /Delete /TN ".engine" /F
pause
