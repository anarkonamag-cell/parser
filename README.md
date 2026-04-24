# Локальный Telegram Channel Finder

Локальное веб-приложение для поиска **каналов Telegram** и выгрузки их `@username` в CSV по вашим фильтрам.

## Режимы подключения

- **Без прокси**
- **MTProto** (host/port/secret)
- **SOCKS5** (host/port/login/password)

Можно переключать режим прямо в интерфейсе.

## Новое

- Кнопка «Проверить текущий режим» проверяет выбранный тип прокси.
- Настройки API + proxy сохраняются в `tg_defaults.json`.
- Для SOCKS5 добавлена поддержка авторизации (username/password).

## Запуск

### Windows (быстрый старт)
1. Двойной клик по `start_parser.bat`.
2. Открыть `http://127.0.0.1:5000`.

### Ручной запуск

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Важные замечания

- Язык и страна определяются эвристически по названию/описанию канала.
- Метрики активности рассчитываются по последним сообщениям в окне анализа.
