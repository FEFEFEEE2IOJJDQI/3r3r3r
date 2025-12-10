#!/usr/bin/env python3
"""
Test script for the bot to verify it works correctly.
"""

import sys
from bot import bot_status, bot_greet, bot_echo

def test_bot_status():
    """Test bot status function."""
    result = bot_status()
    assert "работает" in result, "Bot status check failed"
    print("✓ Test bot_status passed")
    return True

def test_bot_greet():
    """Test bot greeting function."""
    result1 = bot_greet()
    result2 = bot_greet("Test")
    assert "Привет" in result1, "Bot greeting failed"
    assert "Test" in result2, "Bot greeting with name failed"
    print("✓ Test bot_greet passed")
    return True

def test_bot_echo():
    """Test bot echo function."""
    test_message = "Test message"
    result = bot_echo(test_message)
    assert test_message in result, "Bot echo failed"
    print("✓ Test bot_echo passed")
    return True

def run_tests():
    """Run all bot tests."""
    print("Запуск тестов бота (Running bot tests)...")
    print()
    
    tests = [
        test_bot_status,
        test_bot_greet,
        test_bot_echo
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"✗ Test {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} error: {e}")
            failed += 1
    
    print()
    print("=" * 60)
    print(f"Результаты (Results): {passed} passed, {failed} failed")
    
    if failed == 0:
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ! БОТ РАБОТАЕТ! ✓")
        print("ALL TESTS PASSED! THE BOT WORKS! ✓")
        print("=" * 60)
        return 0
    else:
        print("НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОШЛИ ✗")
        print("SOME TESTS FAILED ✗")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
