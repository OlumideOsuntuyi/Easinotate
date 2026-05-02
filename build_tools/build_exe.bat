@echo off
REM ============================================================
REM   Easinotate - Windows .exe build script
REM ============================================================
REM   Run from the project root:
REM       build_tools\build_exe.bat
REM ============================================================

setlocal

cd /d "%~dp0\.."

echo.
echo === Easinotate build ===
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python is not on PATH. Install Python 3.9+ and try again.
    exit /b 1
)

echo [1/4] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
)

echo.
echo [2/4] Cleaning previous build artifacts...
if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

echo.
echo [3/4] Running PyInstaller...
python -m PyInstaller --clean build_tools\easinotate.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed.
    exit /b 1
)

echo.
echo [4/4] Done.
echo.
if exist dist\Easinotate.exe (
    echo SUCCESS: dist\Easinotate.exe
    dir dist\Easinotate.exe | find "Easinotate.exe"
) else (
    echo WARNING: expected dist\Easinotate.exe not found.
)

endlocal
