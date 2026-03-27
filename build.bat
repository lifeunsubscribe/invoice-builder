@echo off
REM build.bat - One-command build script for LisaInvoice desktop app
REM Builds frontend with Vite and packages everything into a Windows .exe with PyInstaller

echo Building frontend...
if not exist frontend\ (
    echo ERROR: frontend directory not found!
    echo Please ensure you are running build.bat from the project root.
    pause
    exit /b 1
)
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
  --collect-all weasyprint ^
  --collect-all cairocffi ^
  --collect-all tinycss2 ^
  app/main.py
if errorlevel 1 (
    echo Packaging failed!
    pause
    exit /b 1
)

echo Done. Executable is in dist/LisaInvoice.exe
pause
