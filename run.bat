@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
SET VENV=.venv_pyo
IF NOT EXIST %VENV% (
  py -3.12 -m venv %VENV%
)
CALL %VENV%\Scripts\activate.bat

REM ============================================================================
REM Dev Commands (only available via run.bat, not in built executables)
REM ============================================================================
IF /I "%~1"=="install" GOTO install
IF /I "%~1"=="test" GOTO test
IF /I "%~1"=="analyze" GOTO analyze
IF /I "%~1"=="cleanup" GOTO cleanup
IF /I "%~1"=="clear-cache" GOTO clear_cache
IF /I "%~1"=="validate" GOTO validate
IF /I "%~1"=="build-cli" GOTO build_cli
IF /I "%~1"=="build-gui" GOTO build_gui
IF /I "%~1"=="build" GOTO build_all
IF /I "%~1"=="build-all" GOTO build_all
IF /I "%~1"=="py" GOTO py

REM ============================================================================
REM App Commands (delegate to psm CLI or GUI)
REM ============================================================================
IF /I "%~1"=="psm" GOTO psm
IF /I "%~1"=="gui" GOTO gui
IF /I "%~1"=="help" GOTO help
IF /I "%~1"=="" GOTO help

REM Default: treat as psm CLI command (for backward compatibility)
GOTO psm_implicit

:install
ECHO Installing dependencies from requirements.txt ...
pip install -r requirements.txt
GOTO :EOF

:test
SHIFT
:collect
IF "%~1"=="" GOTO run_pytest
SET ARGS=%ARGS% %1
SHIFT
GOTO collect
:run_pytest
ECHO Running: python -m pytest%ARGS%
python -m pytest%ARGS%
SET TEST_EXIT=%ERRORLEVEL%
IF %TEST_EXIT% EQU 0 GOTO test_success
IF %TEST_EXIT% GEQ 2 (
  REM Possible KeyboardInterrupt or user abort; attempt segmented reruns
  ECHO Detected non-zero exit (%TEST_EXIT%). Attempting segmented test rerun...
  ECHO Collecting test node ids...
  FOR /F "usebackq tokens=*" %%L IN (`python -m pytest --collect-only -q`) DO (
    ECHO %%L>>.all_tests.tmp
  )
  REM Split list roughly in half (42 observed breakpoint) and run remaining tests separately.
  SET COUNT=0
  FOR /F "usebackq tokens=*" %%L IN (`type .all_tests.tmp`) DO (
    SET /A COUNT+=1
    IF !COUNT! LEQ 42 ECHO %%L>>.segment1.tmp
    IF !COUNT! GTR 42 ECHO %%L>>.segment2.tmp
  )
  ECHO Re-running first segment (up to 42)...
  python -m pytest -q @.segment1.tmp
  IF ERRORLEVEL 1 GOTO after_segments
  ECHO Re-running second segment (remaining)...
  python -m pytest -q @.segment2.tmp
  :after_segments
  DEL /Q .all_tests.tmp 2>NUL
  DEL /Q .segment1.tmp 2>NUL
  DEL /Q .segment2.tmp 2>NUL
)
:test_success
GOTO :EOF

:analyze
SHIFT
SET AMODE=%1
IF "%AMODE%"=="" SET AMODE=changed
SHIFT
SET ANALYZE_ARGS=%AMODE%
:collect_analyze
IF "%~1"=="" GOTO run_analyze
SET ANALYZE_ARGS=%ANALYZE_ARGS% %1
SHIFT
GOTO collect_analyze
:run_analyze
ECHO Running code analysis in %AMODE% mode...
python scripts\analyze_code.py %ANALYZE_ARGS%
GOTO :EOF

:cleanup
SHIFT
SET CMODE=%1
IF "%CMODE%"=="" SET CMODE=changed
SHIFT
SET CLEANUP_ARGS=%CMODE%
:collect_cleanup
IF "%~1"=="" GOTO run_cleanup
SET CLEANUP_ARGS=%CLEANUP_ARGS% %1
SHIFT
GOTO collect_cleanup
:run_cleanup
ECHO Running code cleanup in %CMODE% mode...
python scripts\cleanup_code.py %CLEANUP_ARGS%
GOTO :EOF

:clear_cache
ECHO Clearing Python cache files...
FOR /D /R . %%d IN (__pycache__) DO @IF EXIST "%%d" (
  ECHO Removing %%d
  RD /S /Q "%%d"
)
FOR /R . %%f IN (*.pyc *.pyo) DO @IF EXIST "%%f" (
  ECHO Removing %%f
  DEL /Q "%%f"
)
ECHO Cache cleared!
GOTO :EOF

:validate
ECHO Running build validation...
scripts\validate_builds.bat
GOTO :EOF

:build_cli
ECHO Building CLI executable with PyInstaller...
pyinstaller psm-cli.spec
IF ERRORLEVEL 1 (
  ECHO Error: CLI build failed!
  GOTO :EOF
)
ECHO CLI build successful: dist\psm-cli.exe
GOTO :EOF

:build_gui
ECHO Building GUI executable with PyInstaller...
pyinstaller psm-gui.spec
IF ERRORLEVEL 1 (
  ECHO Error: GUI build failed!
  GOTO :EOF
)
ECHO GUI build successful: dist\psm-gui.exe
GOTO :EOF

:build_all
ECHO Building both CLI and GUI executables...
CALL :build_cli
CALL :build_gui
ECHO All builds complete!
GOTO :EOF

:help
ECHO ============================================================================
ECHO playlist-sync-matcher Development Runner
ECHO ============================================================================
ECHO.
ECHO Usage: run.bat [command] [args]
ECHO.
ECHO Application Commands (run via psm CLI):
ECHO   run.bat psm [command]     Execute any psm CLI command
ECHO   run.bat gui               Launch desktop GUI
ECHO.
ECHO   Examples:
ECHO     run.bat psm pull        Pull Spotify playlists
ECHO     run.bat psm scan        Scan local music library
ECHO     run.bat psm match       Match tracks
ECHO     run.bat psm build       Full sync pipeline
ECHO     run.bat psm --help      Show all CLI commands
ECHO     run.bat gui             Launch GUI application
ECHO.
ECHO Development Commands (only available via run.bat):
ECHO   install                   Install or update dependencies
ECHO   test [args]               Run pytest (e.g. run.bat test -q tests\unit\)
ECHO   analyze [mode]            Code quality analysis (changed^|all^|files ^<paths^>)
ECHO   cleanup [mode]            Code cleanup (whitespace, unused imports)
ECHO   clear-cache               Remove Python cache files (__pycache__, *.pyc)
ECHO   validate                  Validate built executables
ECHO   py ^<args^>                Run python with args inside venv
ECHO.
ECHO Build Commands (create standalone executables):
ECHO   build                     Build both CLI and GUI executables
ECHO   build-cli                 Build CLI executable only (dist\psm-cli.exe)
ECHO   build-gui                 Build GUI executable only (dist\psm-gui.exe)
ECHO.
ECHO ============================================================================
ECHO For built executables (no venv needed):
ECHO   psm-cli.exe [command]     Direct CLI execution (e.g. psm-cli.exe build)
ECHO   psm-gui.exe               Direct GUI execution
ECHO ============================================================================
EXIT /B 0

:py
REM Run arbitrary python command inside the virtual environment
SHIFT
SET PARGS=
:collect_py
IF "%~1"=="" GOTO run_py
SET PARGS=%PARGS% %1
SHIFT
GOTO collect_py
:run_py
python %PARGS%
GOTO :EOF

REM ============================================================================
REM App Command Handlers
REM ============================================================================

:psm
REM Explicit: run.bat psm <command>
REM Remove 'psm' from args and build new command
SHIFT
SET PSM_ARGS=
:collect_psm_args
IF "%~1"=="" GOTO run_psm
SET PSM_ARGS=%PSM_ARGS% %1
SHIFT
GOTO collect_psm_args
:run_psm
IF "%PSM_ARGS%"=="" (
  python -m psm.cli --help
) ELSE (
  python -m psm.cli %PSM_ARGS%
)
GOTO :EOF

:psm_implicit
REM Implicit: run.bat <command> (backward compatibility)
python -m psm.cli %*
GOTO :EOF

:gui
python -m psm.gui
GOTO :EOF
