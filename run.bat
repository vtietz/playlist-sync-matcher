@echo off
SET VENV=.venv
IF NOT EXIST %VENV% (
  py -3 -m venv %VENV%
)
CALL %VENV%\Scripts\activate.bat
pip install -q -r requirements.txt
python -m spx.cli %*
