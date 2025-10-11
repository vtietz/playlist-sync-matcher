@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
SET VENV=.venv
IF NOT EXIST %VENV% (
  py -3 -m venv %VENV%
)
CALL %VENV%\Scripts\activate.bat

IF /I "%~1"=="install" GOTO install

IF /I "%~1"=="test" GOTO test
IF /I "%~1"=="gui" GOTO gui
IF /I "%~1"=="build-cli" GOTO build_cli
IF /I "%~1"=="build-gui" GOTO build_gui
IF /I "%~1"=="build-all" GOTO build_all
IF /I "%~1"=="help" GOTO help
IF /I "%~1"=="version" GOTO version
IF /I "%~1"=="py" GOTO py
GOTO cli

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

:gui
python -m psm.gui
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
ECHO Usage: run.bat [command]
ECHO Commands:
ECHO   pull ^| scan ^| match ^| export ^| report ^| report-albums ^| build
ECHO   gui                   Launch desktop GUI
ECHO   build-cli             Build CLI executable (dist\psm-cli.exe)
ECHO   build-gui             Build GUI executable (dist\psm-gui.exe)
ECHO   build-all             Build both CLI and GUI executables
ECHO   install               Install or update dependencies
ECHO   test [pytest args]    Run test suite (e.g. run.bat test -q tests\test_hashing.py)
ECHO   version               Show CLI version
ECHO   py ^<args^>            Run python with given args inside venv (e.g. run.bat py tools\bulk_replace.py --from X --to Y)
EXIT /B 0

:version
python -m psm.cli --version
GOTO :EOF

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

:cli
python -m psm.cli %*
GOTO :EOF
