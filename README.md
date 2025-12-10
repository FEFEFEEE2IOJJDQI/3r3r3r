# 3r3r3r

## Бот работает? (Does the bot work?)

**Ответ: ДА! ✓** (Answer: YES! ✓)

Этот репозиторий содержит простого рабочего бота для демонстрации функциональности.
(This repository contains a simple working bot to demonstrate functionality.)

## Использование (Usage)

### Запустить бота (Run the bot):
```bash
python3 bot.py
```

### Запустить тесты (Run tests):
```bash
python3 test_bot.py
```

## Функции бота (Bot Functions)

- `bot_status()` - Проверка статуса бота (Check bot status)
- `bot_greet(name)` - Приветствие (Greeting)
- `bot_echo(message)` - Эхо сообщения (Echo message)
- `handle_command(command)` - Обработка команд (Command handling)
  - `/s` - Тихое переключение роли (Silent role switch) - НЕ отправляет сообщение об изменении (does NOT send change message)

## Требования (Requirements)

- Python 3.6+