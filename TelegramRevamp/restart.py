#!/usr/bin/env python3
"""Скрипт для перезапуска бота"""
import os
import signal
import subprocess
import time

print("🛑 Останавливаем старый процесс бота...")

# Найти и убить процесс
try:
    result = subprocess.run(
        ["pgrep", "-f", "python3 main.py"],
        capture_output=True,
        text=True
    )
    
    if result.stdout.strip():
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGKILL)
                print(f"  ✓ Остановлен процесс {pid}")
            except:
                pass
    else:
        print("  Процесс не найден")
except Exception as e:
    print(f"  Ошибка: {e}")

time.sleep(2)

print("🚀 Запускаем бота...")
os.chdir("/workspaces/3r3r3r/TelegramRevamp")
os.execv("/usr/bin/python3", ["python3", "main.py"])
