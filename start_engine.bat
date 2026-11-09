@echo off
REM Starts the .engine server (no window UI). Run as Administrator for ports 53/80.
REM Works from the repo folder or from the deploy folder.
cd /d "%~dp0"
if not exist engine_core.py cd /d "%~dp0.."
python engine_core.py serve
