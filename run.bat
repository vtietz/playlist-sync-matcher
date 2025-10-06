@echo off
SETLOCAL ENABLEDELAYEDEXPANSION
SET VENV=.venv
IF NOT EXIST %VENV% (
  py -3 -m venv %VENV%
)
CALL %VENV%\Scripts\activate.bat

IF /I "%~1"=="install" GOTO install

IF /I "%~1"=="test" GOTO test
IF /I "%~1"=="help" GOTO help
IF /I "%~1"=="version" GOTO version
IF /I "%~1"=="py" GOTO py
:install
ECHO Installing dependencies from requirements.txt ...
pip install -r requirements.txt
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
IF ERRORLEVEL 2 (
  REM Possible KeyboardInterrupt or user abort; attempt segmented reruns
  ECHO Detected non-zero exit (%%ERRORLEVEL%%). Attempting segmented test rerun...
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
GOTO :EOF

:help
ECHO Usage: run.bat [command]
ECHO Commands:
ECHO   pull ^| scan ^| match ^| export ^| report ^| report-albums ^| build
ECHO   install               Install or update dependencies
ECHO   test [pytest args]    Run test suite (e.g. run.bat test -q tests\test_hashing.py)
ECHO   version               Show CLI version
ECHO   py <args>              Run python with given args inside venv (e.g. run.bat py tools\bulk_replace.py --from X --to Y)
GOTO :EOF

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
