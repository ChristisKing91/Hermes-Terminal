@echo off
setlocal
cd /d "%~dp0"
python -c "import PyInstaller, hermes_terminal" >nul 2>&1
if errorlevel 1 (
  echo Activate a Windows Python environment and install this project plus PyInstaller first.
  echo See README.md for instructions. No packages are installed by this script.
  exit /b 1
)
python -m PyInstaller --noconfirm --clean --onefile --console --name LXRION-Terminal --icon assets\branding\app.ico --paths src packaging\windows_entry.py
if errorlevel 1 exit /b 1
echo Built dist\LXRION-Terminal.exe
endlocal
