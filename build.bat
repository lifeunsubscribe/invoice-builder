@echo off
REM build.bat - One-command build script for LisaInvoice desktop app
REM Builds frontend with Vite and packages everything into a Windows .exe with PyInstaller

echo ========================================
echo Building LisaInvoice Desktop App
echo ========================================
echo.

REM Step 1: Build the frontend
echo [1/2] Building frontend with Vite...
cd frontend
call npm run build
if errorlevel 1 (
    echo ERROR: Frontend build failed!
    cd ..
    pause
    exit /b 1
)
cd ..
echo Frontend build complete: dist/ folder ready
echo.

REM Step 2: Package with PyInstaller
echo [2/2] Packaging executable with PyInstaller...
pyinstaller --onefile --windowed ^
  --name="LisaInvoice" ^
  --add-data "frontend/dist;dist" ^
  app/main.py

if errorlevel 1 (
    echo ERROR: PyInstaller packaging failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build Complete!
echo ========================================
echo Executable location: dist/LisaInvoice.exe
echo.
echo Note: The .exe can now be distributed to a clean Windows machine.
echo On first run, Windows SmartScreen will show a warning - click "More info" then "Run anyway".
echo.

pause
