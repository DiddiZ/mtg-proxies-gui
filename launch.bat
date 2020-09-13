@echo off

REM Update
git pull --ff-only
IF %ERRORLEVEL% NEQ 0 ( 
   pause
   EXIT /B 1
)

REM  Install pipenv
python -m pip install --user -U pipenv
IF %ERRORLEVEL% NEQ 0 ( 
   pause
   EXIT /B 1
)

REM  Install dependencies
pipenv install --deploy
IF %ERRORLEVEL% NEQ 0 ( 
   pause
   EXIT /B 1
)

pipenv run python .\gui.py
pause
