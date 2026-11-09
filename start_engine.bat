@echo off
REM Starts the .engine server (no window UI). Run as Administrator for ports 53/80.
cd /d "%~dp0.."
python engine_core.py serve
