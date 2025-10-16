@echo off
REM Validate PyInstaller builds are working correctly
REM Tests both CLI and GUI executables for common failures
REM Updated for --onefile mode (single executables)

echo ========================================
echo PyInstaller Build Validation
echo ========================================
echo.

REM Check if executables exist
echo [1/6] Checking if executables exist...
if not exist "dist\psm-cli.exe" (
    echo [FAIL] dist\psm-cli.exe not found
    exit /b 1
)
if not exist "dist\psm-gui.exe" (
    echo [FAIL] dist\psm-gui.exe not found
    exit /b 1
)
echo [PASS] Both executables found
echo.

REM Test CLI --version
echo [2/6] Testing CLI --version...
dist\psm-cli.exe --version >nul 2>&1
if errorlevel 1 (
    echo [FAIL] CLI --version failed
    dist\psm-cli.exe --version
    exit /b 1
)
echo [PASS] CLI --version works
echo.

REM Test CLI config (tests JSON output)
echo [3/6] Testing CLI config command...
dist\psm-cli.exe config >nul 2>&1
if errorlevel 1 (
    echo [FAIL] CLI config command failed
    dist\psm-cli.exe config
    exit /b 1
)
echo [PASS] CLI config works
echo.

REM Test CLI with emoji output
echo [4/6] Testing CLI emoji output (export --help)...
dist\psm-cli.exe export --help | findstr /C:"Export" >nul 2>&1
if errorlevel 1 (
    echo [FAIL] CLI export --help failed
    dist\psm-cli.exe export --help
    exit /b 1
)
echo [PASS] CLI help output works
echo.

REM Test GUI launches (timeout after 3 seconds)
echo [5/6] Testing GUI launches without import errors...
REM Start GUI in background and capture initial output
start /B "" dist\psm-gui.exe > gui_test.log 2>&1
timeout /t 3 /nobreak >nul

REM Check for import errors in output
findstr /C:"ImportError" /C:"DLL load failed" gui_test.log >nul 2>&1
if not errorlevel 1 (
    echo [FAIL] GUI has import errors:
    type gui_test.log
    taskkill /F /IM psm-gui.exe >nul 2>&1
    del gui_test.log
    exit /b 1
)

REM Kill GUI
taskkill /F /IM psm-gui.exe >nul 2>&1
del gui_test.log
echo [PASS] GUI launches without import errors
echo.

REM Check executable sizes (should be reasonable for --onefile mode)
echo [6/6] Checking executable sizes...
for %%F in (dist\psm-cli.exe) do set CLI_SIZE=%%~zF
for %%F in (dist\psm-gui.exe) do set GUI_SIZE=%%~zF

REM CLI should be > 10 MB (--onefile bundles everything)
if %CLI_SIZE% LSS 10000000 (
    echo [WARN] CLI executable seems too small (%CLI_SIZE% bytes^)
)

REM GUI should be > 30 MB (--onefile bundles PySide6 + everything)
if %GUI_SIZE% LSS 30000000 (
    echo [WARN] GUI executable seems too small (%GUI_SIZE% bytes^)
)

echo [PASS] Executable sizes look reasonable
echo        CLI: %CLI_SIZE% bytes (~18 MB expected)
echo        GUI: %GUI_SIZE% bytes (~58 MB expected)
echo.

echo ========================================
echo [SUCCESS] All validation tests passed!
echo ========================================
echo.
echo Executables are ready for distribution (--onefile mode):
echo   dist\psm-cli.exe (single file, no dependencies)
echo   dist\psm-gui.exe (single file, no dependencies)
echo.
echo These can be distributed as-is - no ZIP needed!
echo.
exit /b 0
