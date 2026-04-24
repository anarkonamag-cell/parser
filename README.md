# Локальный Telegram Channel Finder

Локальное веб-приложение для поиска **каналов Telegram** и выгрузки их `@username` в CSV по вашим фильтрам.

## Новое

- Используется MTProto-прокси (host/port/secret) вместо SOCKS5.
- Добавлена кнопка проверки MTProto endpoint перед запуском парсинга.
- API ID / API HASH / телефон / MTProto сохраняются локально в `tg_defaults.json`.
- Добавлен фильтр стран, включая `germany`.

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

## Проверка MTProto

1. Нажмите кнопку **"Проверить MTProto"**.
2. Если проверка проходит, запускайте парсинг.
3. Если нет — проверьте host/port/secret у провайдера прокси.

## Важные замечания

- Язык и страна определяются эвристически по названию/описанию канала.
- Метрики активности рассчитываются по последним сообщениям в окне анализа.
