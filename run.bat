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
GOTO cli

:install
ECHO Installing dependencies from requirements.txt ...
pip install -r requirements.txt
GOTO :EOF

:test
SHIFT
REM Reconstruct args after shift (since %* was expanded earlier in block contexts)
SET ARGS=
:collect
IF "%~1"=="" GOTO run_pytest
SET ARGS=%ARGS% %1
SHIFT
GOTO collect
:run_pytest
ECHO Running: python -m pytest%ARGS%
python -m pytest%ARGS%
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
