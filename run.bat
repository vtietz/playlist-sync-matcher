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
GOTO :EOF

:version
python -m spx.cli --version
GOTO :EOF

:cli
python -m spx.cli %*
