@echo off
REM ===================================================================
REM  Build MarkItDown Converter into a standalone Windows executable.
REM  Just double-click this file (or run it in a terminal).
REM
REM  Requirements: Python 3.10 - 3.13 installed and on PATH.
REM                Check with:  python --version
REM ===================================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo ==== MarkItDown Converter - build ====
echo.

REM --- locate a Python launcher ---
where py >nul 2>nul && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH.
  echo         Install Python 3.10-3.13 from https://www.python.org/downloads/
  echo         and tick "Add python.exe to PATH" during setup.
  goto :fail
)
for /f "delims=" %%v in ('%PY% --version') do echo Using %%v

REM --- create / reuse a local virtual environment ---
if not exist ".venv" (
  echo Creating virtual environment ^(.venv^)...
  %PY% -m venv .venv || goto :fail
)
call ".venv\Scripts\activate.bat" || goto :fail

REM --- install dependencies ---
echo Upgrading pip...
python -m pip install --upgrade pip >nul
echo Installing dependencies ^(this downloads onnxruntime/pandas; first run is slow^)...
python -m pip install -r requirements.txt || goto :fail

REM --- build ---
echo.
echo Building executable with PyInstaller...
python -m PyInstaller --clean --noconfirm MarkItDown-GUI.spec || goto :fail

echo.
echo ==== BUILD SUCCEEDED ====
if exist "dist\MarkItDownConverter.exe" (
  echo Your app:  "%cd%\dist\MarkItDownConverter.exe"
) else (
  echo Your app folder:  "%cd%\dist\MarkItDownConverter\"
)
echo.
echo Opening the dist folder...
start "" "%cd%\dist"
goto :done

:fail
echo.
echo ==== BUILD FAILED ==== (see messages above)
:done
echo.
pause
endlocal
