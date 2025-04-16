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
for /f "delims=" %%v in ('python --version 2^>nul') do set "PYTHON_VERSION=%%v"
echo [INFO] Python version:
echo   %PYTHON_VERSION%
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
:: Create venv if it doesn't exist
if not exist "%VENV_DIR%\" (
    echo [INFO] Creating virtual environment...
    python -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )

    echo [INFO] Installing dependencies into venv...
    call "%VENV_DIR%\Scripts\activate.bat"
    python -m pip install -r "%REQUIREMENTS%"
    if errorlevel 1 (
        echo [ERROR] Pip failed to install some or all requirements.
        deactivate
        pause
        exit /b 1
    )
    deactivate
    echo [INFO] Dependencies installed successfully.
    echo.
) else (
    echo [INFO] Virtual environment already exists. Skipping setup.
    echo.
)

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
exit /b 0
