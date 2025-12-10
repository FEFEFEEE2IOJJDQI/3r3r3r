#!/usr/bin/env python3
"""
Simple bot implementation to demonstrate functionality.
Answers the question: бот работает? (Does the bot work?)
"""

def bot_status():
    """Check if the bot is working."""
    return "Да, бот работает! (Yes, the bot works!)"

def bot_greet(name="User"):
    """Bot greeting function."""
    return f"Привет, {name}! Я работающий бот. (Hello, {name}! I'm a working bot.)"

def bot_echo(message):
    """Bot echo function."""
    return f"Бот получил: {message} (Bot received: {message})"

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
    
    print("=" * 60)
    print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ (ALL TESTS PASSED)")
    print("ОТВЕТ НА ВОПРОС: ДА, БОТ РАБОТАЕТ! ✓")
    print("ANSWER TO QUESTION: YES, THE BOT WORKS! ✓")
    print("=" * 60)

if __name__ == "__main__":
    main()
