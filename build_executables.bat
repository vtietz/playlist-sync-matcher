@echo off
REM Build PyInstaller executables using conda base Python (not venv)
REM This ensures PyInstaller can properly bundle all DLLs

echo Building PyInstaller executables with conda base Python...
echo.

REM Deactivate any active venv
if defined VIRTUAL_ENV (
    echo Deactivating virtualenv...
    deactivate 2>nul
)

REM Use conda base Python directly
set PYTHON_EXE=C:\Users\live\miniconda3\python.exe

REM Verify Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Conda Python not found at %PYTHON_EXE%
    echo Please update PYTHON_EXE path in this script
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" --version
echo.

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo.

REM Build CLI
echo Building CLI executable...
"%PYTHON_EXE%" -m PyInstaller psm-cli.spec --clean
if errorlevel 1 (
    echo ERROR: CLI build failed
    exit /b 1
)
echo CLI build complete
echo.

REM Build GUI
echo Building GUI executable...
"%PYTHON_EXE%" -m PyInstaller psm-gui.spec --clean
if errorlevel 1 (
    echo ERROR: GUI build failed
    exit /b 1
)
echo GUI build complete
echo.

echo ========================================
echo All builds complete!
echo CLI: dist\psm-cli.exe
echo GUI: dist\psm-gui.exe
echo ========================================
