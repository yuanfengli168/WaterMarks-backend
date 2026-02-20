@echo off
REM Startup script for WaterMarks Backend (Windows)

echo Starting WaterMarks Backend...

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env exists
if not exist ".env" (
    echo .env file not found. Creating from .env.example...
    copy .env.example .env
    echo Please edit .env with your configuration
)

REM Create temp directories
echo Creating temporary directories...
if not exist "temp_files" mkdir temp_files
if not exist "temp_files\uploads" mkdir temp_files\uploads
if not exist "temp_files\processing" mkdir temp_files\processing
if not exist "temp_files\outputs" mkdir temp_files\outputs

REM Start the server
echo Starting server...
echo Server will be available at http://localhost:8000
echo API docs available at http://localhost:8000/docs
echo.

python app.py
