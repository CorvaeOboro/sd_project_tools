:: INSTALLER AND LAUNCHER FOR SD PROJECT TOOLS
:: Creates a virtual environment, installs requirements,
:: Launches tools in separate windows with logging and persistent terminals

@echo off
setlocal ENABLEEXTENSIONS

:: Set working directory to script location
cd /d "%~dp0"

:: Configurable paths
set "VENV_DIR=venv"
set "TOOLS_LAUNCHER=launch_tools.py"
set "REQUIREMENTS=requirements.txt"
set "LOG_DIR=logs"

:: Create logs folder if not exist
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

echo ===================================================
echo SD PROJECT TOOLS Installer and Launcher
echo ===================================================
echo.

:: ================================
:: Show current working directory
echo [INFO] Current working directory:
echo   %CD%
echo.

:: ================================
:: Check for Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not found in PATH.
    pause
    exit /b 1
)

:: ================================
:: Print Python path and version
for /f "delims=" %%i in ('where python') do set "PYTHON_PATH=%%i"
echo [INFO] Python path:
echo   %PYTHON_PATH%
for /f "tokens=2 delims= " %%v in ('python --version 2^>nul') do set "PYTHON_VERSION=%%v"
echo [INFO] Python version:
echo   %PYTHON_VERSION%

:: Check Python version is 3.10.x
setlocal enabledelayedexpansion
set "_VER_OK=0"
for /f "tokens=1,2 delims=. " %%a in ("%PYTHON_VERSION%") do (
    if "%%a"=="3" if "%%b"=="10" set "_VER_OK=1"
)
if not !_VER_OK! == 1 (
    echo [WARNING] Python 3.10.x is required. Current version: %PYTHON_VERSION%
    echo Attempting to locate another Python 3.10 installation...
    set "PYTHON310_PATH="
    :: Search for python3.10.exe or python310.exe in PATH
    for %%P in (python3.10.exe python310.exe) do (
        for /f "delims=" %%X in ('where %%P 2^>nul') do (
            set "PYTHON310_PATH=%%X"
        )
    )
    :: Check common install locations
    if not defined PYTHON310_PATH if exist "C:\Python310\python.exe" set "PYTHON310_PATH=C:\Python310\python.exe"
    if not defined PYTHON310_PATH if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PYTHON310_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    if not defined PYTHON310_PATH if exist "%ProgramFiles%\Python310\python.exe" set "PYTHON310_PATH=%ProgramFiles%\Python310\python.exe"
    if defined PYTHON310_PATH (
        echo [INFO] Found Python 3.10 at: !PYTHON310_PATH!
        set /p USE310="Use this Python for setup? (y/n): "
        if /i "!USE310!"=="y" (
            set "PYTHON_PATH=!PYTHON310_PATH!"
            set "PYTHON_EXE=!PYTHON310_PATH!"
            set "PYTHON_VERSION="
            for /f "tokens=2 delims= " %%v in ('"!PYTHON310_PATH!" --version 2^>nul') do set "PYTHON_VERSION=%%v"
            echo [INFO] Using Python: !PYTHON310_PATH!
        ) else (
            echo Aborting.
            exit /b 1
        )
    ) else (
        echo [ERROR] No Python 3.10 installation found.
        echo Please download and install Python 3.10 from:
        echo   https://www.python.org/downloads/release/python-3100/
        echo After installation, re-run this script.
        pause
        exit /b 1
    )
)
endlocal

echo.
:: ================================
:: Check for pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip is not installed or not working.
    pause
    exit /b 1
)
for /f "delims=" %%p in ('python -m pip --version') do set "PIP_VERSION=%%p"
echo [INFO] Pip version:
echo   %PIP_VERSION%
:: Check pip is from Python 3.10
python -m pip --version | findstr /C:"python 3.10" >nul
if errorlevel 1 (
    echo [WARNING] pip is not from Python 3.10. Please ensure you are using the correct Python.
    set /p CONTINUE="Continue anyway? (y/n): "
    if /i not "!CONTINUE!"=="y" (
        echo Aborting.
        exit /b 1
    )
)
echo.

:: ================================
:: Show virtual environment path
echo [INFO] Virtual environment path:
echo   %CD%\%VENV_DIR%
echo.

:: ================================
:: Show requirements to install
if exist "%REQUIREMENTS%" (
    echo [INFO] Requirements.txt found at:
    echo   %CD%\%REQUIREMENTS%
    echo.
    echo [INFO] Requirements:
    type "%REQUIREMENTS%"
    echo.
) else (
    echo [ERROR] requirements.txt not found!
    pause
    exit /b 1
)

:: ================================
:: ================================
:: Check for venv and requirements freshness
set "VENV_OK=1"
if exist "%VENV_DIR%\" (
    echo [INFO] Virtual environment already exists. Checking integrity...
    if not exist "%VENV_DIR%\Scripts\activate.bat" set "VENV_OK=0"
    if not exist "%VENV_DIR%\Scripts\python.exe" set "VENV_OK=0"
    if not exist "%VENV_DIR%\Scripts\pip.exe" set "VENV_OK=0"
    if %VENV_OK%==0 (
        echo [WARNING] Existing venv appears incomplete or broken.
        set /p DELVENV="Delete and recreate venv? (y/n): "
        if /i "%DELVENV%"=="y" (
            rmdir /s /q "%VENV_DIR%"
            if exist "%VENV_DIR%\" (
                echo [ERROR] Failed to delete venv folder.
                pause
                exit /b 1
            )
        ) else (
            echo Aborting setup due to incomplete venv.
            exit /b 1
        )
    )
)
:: If venv exists and is valid, check requirements freshness
if exist "%VENV_DIR%\" if %VENV_OK%==1 (
    setlocal enabledelayedexpansion
    set "VENVTIME="
    set "REQTIME="
    for %%F in ("%VENV_DIR%\Scripts\activate.bat") do set "VENVTIME=%%~tF"
    for %%F in ("%REQUIREMENTS%") do set "REQTIME=%%~tF"
    set "NEEDS_INSTALL=0"
    if defined VENVTIME if defined REQTIME (
        if "!REQTIME!" GTR "!VENVTIME!" set "NEEDS_INSTALL=1"
    )
    if "!NEEDS_INSTALL!"=="1" (
        echo [INFO] requirements.txt is newer than venv. Reinstall dependencies is recommended.
        set /p REINSTALL="Reinstall dependencies? (y/n): "
        if /i "!REINSTALL!"=="y" goto :install_requirements
        echo [INFO] Skipping dependency reinstall. Launching tools...
        endlocal
        goto :launch_tools
    ) else (
        echo [INFO] Virtual environment and dependencies already installed and up-to-date.
        endlocal
        goto :launch_tools
    )
)

if not exist "%VENV_DIR%\" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)
:install_requirements
:: ================================
:: Install requirements
call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install -r "%REQUIREMENTS%"
if errorlevel 1 (
    echo [ERROR] Pip failed to install some or all requirements.
    deactivate
    set /p RECREATE="Delete and recreate venv and try again? (y/n): "
    if /i "%RECREATE%"=="y" (
        deactivate
        rmdir /s /q "%VENV_DIR%"
        if exist "%VENV_DIR%\" (
            echo [ERROR] Failed to delete venv folder.
            pause
            exit /b 1
        )
        echo [INFO] Recreating virtual environment 
        python -m venv "%VENV_DIR%"
        if errorlevel 1 (
            echo [ERROR] Failed to create virtual environment.
            pause
            exit /b 1
        )
        call "%VENV_DIR%\Scripts\activate.bat"
        python -m pip install -r "%REQUIREMENTS%"
        if errorlevel 1 (
            echo [ERROR] Pip failed again. Aborting.
            deactivate
            pause
            exit /b 1
        )
    ) else (
        echo Aborting due to failed dependency install.
        deactivate
        exit /b 1
    )
)
deactivate
echo [INFO] Dependencies installed successfully.
echo.
:launch_tools

:: ================================
:: Launch tools in separate persistent terminals
echo [INFO] Tool Launcher opening in virtual environment
echo.

:: Launch REVIEW_TOOL with log
start "Launch Tool" cmd /k echo ============================== ^& echo [Tool 1: %TOOLS_LAUNCHER%] ^& echo ============================== ^& call %CD%\%VENV_DIR%\Scripts\activate.bat ^& python %CD%\%TOOLS_LAUNCHER% >> %CD%\%LOG_DIR%\launch_tool_log.txt 2>&1

echo.
echo [INFO] Launch tool opened
echo [INFO] Logs saved in: %LOG_DIR%
echo.

endlocal
pause
::exit /b 0
