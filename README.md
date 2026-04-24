# Локальный Telegram Channel Finder

Локальное веб-приложение для поиска **каналов Telegram** и выгрузки их `@username` в CSV по вашим фильтрам.

## Новое

- API ID / API HASH / телефон сохраняются локально в `tg_defaults.json` (не нужно вводить каждый раз).
- Добавлены фильтры по нескольким языкам и нескольким странам.
- Добавлены поля SOCKS5-прокси для случаев, когда Telegram не подключается (TimeoutError).
- Добавлен `start_parser.bat` для запуска через двойной клик в Windows.

## Запуск

### Windows (быстрый старт)

1. Двойной клик по `start_parser.bat`.
2. Браузер: `http://127.0.0.1:5000`.

### Ручной запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Почему был TimeoutError

Сообщение `Attempt N at connecting failed: TimeoutError` означает, что клиент Telethon не смог подключиться к серверам Telegram из вашей сети.
Используйте SOCKS5-прокси в форме или другую сеть.

## Важные замечания

- Язык и страна определяются эвристически по названию/описанию канала.
- Метрики активности рассчитываются по последним сообщениям в окне анализа.
