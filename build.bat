@echo off
REM build.bat - One-command build script for LisaInvoice desktop app
REM Builds frontend with Vite and packages everything into a Windows .exe with PyInstaller

echo Building frontend...
cd frontend
call npm run build
cd ..

echo Packaging executable...
pyinstaller --onefile --windowed ^
  --icon=frontend/public/icon.ico ^
  --name="LisaInvoice" ^
  --add-data "frontend/dist;dist" ^
  app/main.py

echo Done. Executable is in dist/LisaInvoice.exe
pause
