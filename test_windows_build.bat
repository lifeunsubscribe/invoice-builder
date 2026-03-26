@echo off
REM test_windows_build.bat - Automated Windows build testing script
REM Tests the full PyInstaller build and packaging process
REM Validates acceptance criteria for Phase 4 testing

setlocal enabledelayedexpansion

echo ============================================================
echo Lisa Invoice Builder - Windows Build Test Suite
echo ============================================================
echo.
echo Test started: %date% %time%
echo.

REM Initialize results log
set LOG_FILE=test_results.log
echo Lisa Invoice Builder - Windows Build Test Results > %LOG_FILE%
echo Test Date: %date% %time% >> %LOG_FILE%
echo. >> %LOG_FILE%

set PASS_COUNT=0
set FAIL_COUNT=0

REM ============================================================
REM Test 1: Prerequisites Check
REM ============================================================
echo [Test 1] Checking prerequisites...
echo [Test 1] Prerequisites Check >> %LOG_FILE%

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Python not found
    echo   FAIL - Python not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VER=%%i
    echo   [PASS] !PYTHON_VER!
    echo   PASS - !PYTHON_VER! >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] Node.js not found
    echo   FAIL - Node.js not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    for /f "tokens=*" %%i in ('node --version 2^>^&1') do set NODE_VER=%%i
    echo   [PASS] Node.js !NODE_VER!
    echo   PASS - Node.js !NODE_VER! >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

REM Check npm
npm --version >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] npm not found
    echo   FAIL - npm not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    for /f "tokens=*" %%i in ('npm --version 2^>^&1') do set NPM_VER=%%i
    echo   [PASS] npm !NPM_VER!
    echo   PASS - npm !NPM_VER! >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

REM Check PyInstaller
python -c "import PyInstaller; print(PyInstaller.__version__)" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] PyInstaller not installed
    echo   FAIL - PyInstaller not installed >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    for /f "tokens=*" %%i in ('python -c "import PyInstaller; print(PyInstaller.__version__)" 2^>^&1') do set PYINST_VER=%%i
    echo   [PASS] PyInstaller !PYINST_VER!
    echo   PASS - PyInstaller !PYINST_VER! >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

REM Check WeasyPrint
python -c "import weasyprint; print(weasyprint.__version__)" >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] WeasyPrint not installed
    echo   FAIL - WeasyPrint not installed >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    for /f "tokens=*" %%i in ('python -c "import weasyprint; print(weasyprint.__version__)" 2^>^&1') do set WEASY_VER=%%i
    echo   [PASS] WeasyPrint !WEASY_VER!
    echo   PASS - WeasyPrint !WEASY_VER! >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 2: Project Structure Validation
REM ============================================================
echo.
echo [Test 2] Validating project structure...
echo [Test 2] Project Structure Validation >> %LOG_FILE%

if not exist build.bat (
    echo   [FAIL] build.bat not found
    echo   FAIL - build.bat not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] build.bat exists
    echo   PASS - build.bat exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

if not exist app\main.py (
    echo   [FAIL] app\main.py not found
    echo   FAIL - app\main.py not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] app\main.py exists
    echo   PASS - app\main.py exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

if not exist frontend\package.json (
    echo   [FAIL] frontend\package.json not found
    echo   FAIL - frontend\package.json not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] frontend\package.json exists
    echo   PASS - frontend\package.json exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

if not exist frontend\public\icon.ico (
    echo   [FAIL] frontend\public\icon.ico not found
    echo   FAIL - frontend\public\icon.ico not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] frontend\public\icon.ico exists
    echo   PASS - frontend\public\icon.ico exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 3: Clean Previous Build Artifacts
REM ============================================================
echo.
echo [Test 3] Cleaning previous build artifacts...
echo [Test 3] Cleaning Build Artifacts >> %LOG_FILE%

if exist dist\LisaInvoice.exe (
    del dist\LisaInvoice.exe
    echo   [INFO] Removed previous dist\LisaInvoice.exe
    echo   INFO - Removed previous dist\LisaInvoice.exe >> %LOG_FILE%
)

if exist LisaInvoice.spec (
    del LisaInvoice.spec
    echo   [INFO] Removed previous LisaInvoice.spec
    echo   INFO - Removed previous LisaInvoice.spec >> %LOG_FILE%
)

if exist build (
    rmdir /s /q build
    echo   [INFO] Removed previous build\ directory
    echo   INFO - Removed previous build\ directory >> %LOG_FILE%
)

echo   [PASS] Build artifacts cleaned
echo   PASS - Build artifacts cleaned >> %LOG_FILE%
set /a PASS_COUNT+=1

echo. >> %LOG_FILE%

REM ============================================================
REM Test 4: Run Build Process
REM ============================================================
echo.
echo [Test 4] Running build.bat...
echo [Test 4] Build Process Execution >> %LOG_FILE%
echo   This may take 2-5 minutes...

REM Run build and capture output
call build.bat > build_output.log 2>&1

if errorlevel 1 (
    echo   [FAIL] Build failed - see build_output.log for details
    echo   FAIL - Build failed >> %LOG_FILE%
    echo. >> %LOG_FILE%
    echo   Build output: >> %LOG_FILE%
    type build_output.log >> %LOG_FILE%
    set /a FAIL_COUNT+=1
    goto :test_summary
) else (
    echo   [PASS] Build completed successfully
    echo   PASS - Build completed successfully >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 5: Verify Exe Creation
REM ============================================================
echo.
echo [Test 5] Verifying LisaInvoice.exe creation...
echo [Test 5] Executable Creation Verification >> %LOG_FILE%

if not exist dist\LisaInvoice.exe (
    echo   [FAIL] dist\LisaInvoice.exe not created
    echo   FAIL - dist\LisaInvoice.exe not created >> %LOG_FILE%
    set /a FAIL_COUNT+=1
    goto :test_summary
) else (
    echo   [PASS] dist\LisaInvoice.exe exists
    echo   PASS - dist\LisaInvoice.exe exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

REM Check file size
for %%A in (dist\LisaInvoice.exe) do set EXE_SIZE=%%~zA
set /a EXE_SIZE_MB=!EXE_SIZE! / 1048576

echo   [INFO] Exe file size: !EXE_SIZE_MB! MB
echo   INFO - Exe file size: !EXE_SIZE_MB! MB >> %LOG_FILE%

if !EXE_SIZE_MB! LSS 10 (
    echo   [WARN] Exe size suspiciously small ^(!EXE_SIZE_MB! MB^) - may be incomplete
    echo   WARN - Exe size suspiciously small ^(!EXE_SIZE_MB! MB^) >> %LOG_FILE%
) else if !EXE_SIZE_MB! GTR 500 (
    echo   [WARN] Exe size very large ^(!EXE_SIZE_MB! MB^) - may have bundling issues
    echo   WARN - Exe size very large ^(!EXE_SIZE_MB! MB^) >> %LOG_FILE%
) else (
    echo   [PASS] Exe size within expected range ^(10-500 MB^)
    echo   PASS - Exe size within expected range ^(!EXE_SIZE_MB! MB^) >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 6: Verify Frontend Bundle
REM ============================================================
echo.
echo [Test 6] Verifying frontend build output...
echo [Test 6] Frontend Bundle Verification >> %LOG_FILE%

if not exist frontend\dist\index.html (
    echo   [FAIL] frontend\dist\index.html not found
    echo   FAIL - frontend\dist\index.html not found >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] frontend\dist\index.html exists
    echo   PASS - frontend\dist\index.html exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

if not exist frontend\dist\assets (
    echo   [WARN] frontend\dist\assets directory not found
    echo   WARN - frontend\dist\assets directory not found >> %LOG_FILE%
) else (
    echo   [PASS] frontend\dist\assets directory exists
    echo   PASS - frontend\dist\assets directory exists >> %LOG_FILE%
    set /a PASS_COUNT+=1
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 7: PyInstaller Spec File Validation
REM ============================================================
echo.
echo [Test 7] Validating PyInstaller spec file...
echo [Test 7] PyInstaller Spec Validation >> %LOG_FILE%

if not exist LisaInvoice.spec (
    echo   [FAIL] LisaInvoice.spec not generated
    echo   FAIL - LisaInvoice.spec not generated >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] LisaInvoice.spec generated
    echo   PASS - LisaInvoice.spec generated >> %LOG_FILE%
    set /a PASS_COUNT+=1

    REM Check for --windowed mode (console=False)
    findstr /C:"console=False" LisaInvoice.spec >nul 2>&1
    if errorlevel 1 (
        echo   [WARN] Spec file may not be in windowed mode
        echo   WARN - Spec file may not be in windowed mode >> %LOG_FILE%
    ) else (
        echo   [PASS] Windowed mode enabled ^(no console window^)
        echo   PASS - Windowed mode enabled >> %LOG_FILE%
        set /a PASS_COUNT+=1
    )
)

echo. >> %LOG_FILE%

REM ============================================================
REM Test 8: WeasyPrint Import Test
REM ============================================================
echo.
echo [Test 8] Testing WeasyPrint bundling...
echo [Test 8] WeasyPrint Bundling Test >> %LOG_FILE%
echo   Note: Full WeasyPrint test requires running the exe with PDF generation

REM Create minimal test script
echo import sys > weasyprint_test.py
echo try: >> weasyprint_test.py
echo     from weasyprint import HTML, CSS >> weasyprint_test.py
echo     print("WeasyPrint import SUCCESS") >> weasyprint_test.py
echo except Exception as e: >> weasyprint_test.py
echo     print(f"WeasyPrint import FAILED: {e}") >> weasyprint_test.py
echo     sys.exit(1) >> weasyprint_test.py

python weasyprint_test.py >nul 2>&1
if errorlevel 1 (
    echo   [FAIL] WeasyPrint import failed in Python environment
    echo   FAIL - WeasyPrint import failed >> %LOG_FILE%
    set /a FAIL_COUNT+=1
) else (
    echo   [PASS] WeasyPrint imports successfully in Python environment
    echo   PASS - WeasyPrint imports in Python >> %LOG_FILE%
    set /a PASS_COUNT+=1
    echo   [INFO] Full bundled exe test requires manual validation
    echo   INFO - Full bundled exe test requires manual validation >> %LOG_FILE%
)

del weasyprint_test.py >nul 2>&1

echo. >> %LOG_FILE%

REM ============================================================
REM Test Summary
REM ============================================================
:test_summary
echo.
echo ============================================================
echo Test Summary
echo ============================================================
echo. >> %LOG_FILE%
echo ============================================================ >> %LOG_FILE%
echo Test Summary >> %LOG_FILE%
echo ============================================================ >> %LOG_FILE%

set /a TOTAL_TESTS=!PASS_COUNT! + !FAIL_COUNT!
echo Total tests: !TOTAL_TESTS!
echo Passed: !PASS_COUNT!
echo Failed: !FAIL_COUNT!
echo.
echo Total tests: !TOTAL_TESTS! >> %LOG_FILE%
echo Passed: !PASS_COUNT! >> %LOG_FILE%
echo Failed: !FAIL_COUNT! >> %LOG_FILE%
echo. >> %LOG_FILE%

if !FAIL_COUNT! EQU 0 (
    echo [OVERALL STATUS] ALL TESTS PASSED
    echo [OVERALL STATUS] ALL TESTS PASSED >> %LOG_FILE%
    echo.
    echo Next steps:
    echo 1. Test dist\LisaInvoice.exe on this development machine
    echo 2. Test on a clean Windows machine without Python
    echo 3. Verify PDF generation works from bundled exe
    echo 4. Verify email sending works from bundled exe
    echo 5. Document results in docs\PACKAGING_NOTES.md
) else (
    echo [OVERALL STATUS] TESTS FAILED
    echo [OVERALL STATUS] TESTS FAILED >> %LOG_FILE%
    echo.
    echo Please review the failures above and check:
    echo - Are all dependencies installed? ^(pip install -r requirements.txt^)
    echo - Is Node.js and npm configured correctly?
    echo - Does build_output.log contain error details?
)

echo.
echo Test results saved to: %LOG_FILE%
echo Build output saved to: build_output.log
echo.
echo ============================================================
echo Test completed: %date% %time%
echo ============================================================
echo.

pause
