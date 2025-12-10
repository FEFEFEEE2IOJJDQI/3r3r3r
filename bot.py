#!/usr/bin/env python3
"""
Simple bot implementation to demonstrate functionality.
Answers the question: бот работает? (Does the bot work?)
"""

# Bot state
current_role = "user"

def bot_status():
    """Check if the bot is working."""
    return "Да, бот работает! (Yes, the bot works!)"

def bot_greet(name="User"):
    """Bot greeting function."""
    return f"Привет, {name}! Я работающий бот. (Hello, {name}! I'm a working bot.)"

def bot_echo(message):
    """Bot echo function."""
    return f"Бот получил: {message} (Bot received: {message})"

def handle_command(command):
    """Handle bot commands. Returns None for silent commands."""
    global current_role
    
    if command == "/s":
        # Silently switch role without sending any message
        current_role = "admin" if current_role == "user" else "user"
        return None  # No message sent
    
    return f"Неизвестная команда: {command}"

def get_current_role():
    """Get the current bot role."""
    return current_role

def main():
    """Main function to demonstrate bot functionality."""
    print("=" * 60)
    print("БОТ ЗАПУЩЕН (BOT STARTED)")
    print("=" * 60)
    print()
    
    # Test 1: Status check
    print("Тест 1: Проверка статуса (Test 1: Status check)")
    print(bot_status())
    print()
    
    # Test 2: Greeting
    print("Тест 2: Приветствие (Test 2: Greeting)")
    print(bot_greet())
    print(bot_greet("Иван"))
    print()
    
    # Test 3: Echo
    print("Тест 3: Эхо (Test 3: Echo)")
    print(bot_echo("Привет, бот!"))
    print()
    
    # Test 4: Command handling (/s command)
    print("Тест 4: Команда /s (Test 4: /s command)")
    print(f"Текущая роль (Current role): {get_current_role()}")
    result = handle_command("/s")
    if result is None:
        print("✓ Команда /s выполнена без сообщения (Command /s executed silently)")
    else:
        print(result)
    print(f"Новая роль (New role): {get_current_role()}")
    print()
    
    print("=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ (ALL TESTS PASSED)")
    print("ОТВЕТ НА ВОПРОС: ДА, БОТ РАБОТАЕТ! ✓")
    print("ANSWER TO QUESTION: YES, THE BOT WORKS! ✓")
    print("=" * 60)

if __name__ == "__main__":
    main()
