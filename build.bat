@echo off
REM build.bat - One-command build script for LisaInvoice desktop app
REM Builds frontend with Vite and packages everything into a Windows .exe with PyInstaller

echo Building frontend...
cd frontend
call npm run build
if errorlevel 1 (
    echo Frontend build failed!
    cd ..
    pause
    exit /b 1
)
cd ..

echo Packaging executable...
pyinstaller --onefile --windowed ^
  --icon=frontend/public/icon.ico ^
  --name="LisaInvoice" ^
  --add-data "frontend/dist;dist" ^
  app/main.py
if errorlevel 1 (
    echo Packaging failed!
    pause
    exit /b 1
)

echo Done. Executable is in dist/LisaInvoice.exe
pause
