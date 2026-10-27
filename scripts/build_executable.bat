@echo off
REM SPDX-License-Identifier: AGPL-3.0-or-later
REM Build the Emognition standalone (one-folder bundle) with PyInstaller.
REM
REM Usage:  scripts\build_executable.bat
REM Output: dist\emognition\emognition.exe  (a folder; zip it to distribute)
REM
REM Run this on the target Windows machine -- PyInstaller does not cross-compile.

cd /d "%~dp0\.."

if not exist ".venv\Scripts\python.exe" (
    echo No .venv found. See README setup.
    exit /b 1
)

.venv\Scripts\python.exe -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller missing: .venv\Scripts\pip install -r requirements-build.txt
    exit /b 1
)

echo Building Emognition standalone with PyInstaller...
.venv\Scripts\python.exe -m PyInstaller --noconfirm emognition.spec

echo.
echo Built: dist\emognition
echo Verify the bundle (headless) with:
echo     dist\emognition\emognition.exe --selfcheck
