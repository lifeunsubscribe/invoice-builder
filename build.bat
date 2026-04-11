@echo off
REM build.bat - Local one-command build for Invoice Builder.
REM
REM NOTE: the canonical build is .github/workflows/build.yml (GitHub Actions
REM on push to main). This script is kept for offline / ad-hoc local builds.
REM It produces "Invoice Builder.exe" — same name as the CI artifact, so a
REM local build can be a drop-in for testing.
REM
REM Vite's outDir is ../dist (project-root dist/), so the PyInstaller arg
REM is `--add-data "dist;dist"`, NOT `frontend/dist;dist`. Mismatching this
REM produces an exe that exits at startup via _verify_static_assets_or_exit().

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

if not exist dist\index.html (
    echo ERROR: dist\index.html not found after frontend build.
    echo Vite outDir should be '../dist'. Check frontend/vite.config.js.
    pause
    exit /b 1
)

REM Remove any prior exe from dist\ so we don't accidentally bundle it
REM into the new exe (PyInstaller writes its onefile output into dist\
REM and the bundled --add-data "dist;dist" includes everything in dist\).
if exist "dist\Invoice Builder.exe" del /q "dist\Invoice Builder.exe"

echo Packaging executable...
pyinstaller --onefile --windowed --clean ^
  --icon=frontend/public/icon.ico ^
  --name="Invoice Builder" ^
  --add-data "dist;dist" ^
  --add-data "app\templates;app\templates" ^
  --add-data "app\fonts.conf;app" ^
  --collect-all weasyprint ^
  --collect-all cairocffi ^
  --collect-all tinycss2 ^
  app/main.py
if errorlevel 1 (
    echo Packaging failed!
    pause
    exit /b 1
)

echo Done. Executable is in "dist\Invoice Builder.exe"
pause
