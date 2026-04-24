@echo off
chcp 65001 > nul
cd /d "%~dp0"

echo [1/4] Проверка Python...
py --version >nul 2>&1
if errorlevel 1 (
  echo Python launcher 'py' не найден. Установите Python 3.10+ с python.org
  pause
  exit /b 1
)

echo [2/4] Подготовка venv...
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
)

echo [3/4] Установка зависимостей...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo [4/4] Запуск веб-интерфейса...
start http://127.0.0.1:5000
python app.py
pause
