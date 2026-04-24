@echo off
chcp 65001 > nul
cd /d "%~dp0"

set "PY_CMD="
py --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py"
if "%PY_CMD%"=="" (
  python --version >nul 2>&1
  if not errorlevel 1 set "PY_CMD=python"
)

if "%PY_CMD%"=="" (
  echo Не найден Python. Установите Python 3.10+ и добавьте в PATH.
  pause
  exit /b 1
)

echo [1/4] Подготовка venv...
if not exist ".venv\Scripts\python.exe" (
  %PY_CMD% -m venv .venv
)

if not exist ".venv\Scripts\activate.bat" (
  echo Не удалось создать виртуальное окружение.
  pause
  exit /b 1
)

echo [2/4] Активация venv...
call .venv\Scripts\activate.bat

echo [3/4] Установка зависимостей...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Ошибка установки зависимостей.
  pause
  exit /b 1
)

echo [4/4] Запуск веб-интерфейса...
start http://127.0.0.1:5000
python app.py
pause
