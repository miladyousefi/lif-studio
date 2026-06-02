@echo off
REM Build a standalone Windows LIF Studio .exe using PyInstaller.
REM
REM   1) py -m venv venv && venv\Scripts\activate
REM   2) pip install -r requirements.txt pyinstaller
REM   3) packaging\build_exe.bat
REM
REM Output: dist\lif-studio\lif-studio.exe  (a one-folder build).
REM To make a single-file .exe instead, add --onefile to the command below.

cd /d "%~dp0\.."
python -m PyInstaller --noconfirm --clean packaging\lif_studio.spec
echo.
echo Done. Launch: dist\lif-studio\lif-studio.exe
echo (Zip the dist\lif-studio folder to distribute, or build an installer with Inno Setup.)
