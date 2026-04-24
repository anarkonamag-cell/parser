# Локальный Telegram Channel Finder

Локальное веб-приложение для поиска **каналов Telegram** и выгрузки их `@username` в CSV по вашим фильтрам.

## Новое

- Используется MTProto-прокси (host/port/secret) вместо SOCKS5.
- Проверка прокси теперь делает не только TCP, но и Telethon handshake (если заполнены API ID/HASH).
- API ID / API HASH / телефон / MTProto сохраняются локально в `tg_defaults.json`.
- В мультивыбор стран добавлены практически все страны Европы + доп. страны.
- `start_parser.bat` улучшен: fallback с `py` на `python`, понятные ошибки.

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
2. Если проверка проходит с handshake, запускайте парсинг.
3. Если парсинг всё равно не идёт — проверьте корректность secret и тип MTProto транспорта у провайдера.

## Важные замечания

- Язык и страна определяются эвристически по названию/описанию канала.
- Метрики активности рассчитываются по последним сообщениям в окне анализа.
