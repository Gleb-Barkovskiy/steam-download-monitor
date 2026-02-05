# steam-download-monitor

Мониторинг загрузки игр в Steam через анализ логов и ACF-файлов.  
Скрипт выводит имя игры, статус (загрузка, пауза и т.д.) и скорость каждую минуту в течение 5 минут (по умолчанию).

## Установка и запуск

### 1. Клонирование репозитория
```bash
git clone https://github.com/Gleb-Barkovskiy/steam-download-monitor.git
cd steam-download-monitor
```

### 2. Настройка виртуального окружения (рекомендуется)
```bash
# Создать виртуальное окружение
python -m venv venv

# Активировать его
# Linux/macOS:
source venv/bin/activate
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (CMD):
venv\Scripts\activate.bat
```

### 3. Установка зависимостей
```bash
# Установить необходимые зависимости (watchdog)
pip install -e .
# Установить зависимости для разработки 
pip install -e ".[dev]"
```

## Использование

```bash
steam-monitor [ОПЦИИ]
```

### Опции командной строки

| Флаг | По умолчанию | Описание |
|------|---------------|----------|
| `--interval INT` | `60` | Интервал между выборками в секундах. |
| `--samples INT` | `6` | Количество выборок. Если указано `0`, скрипт работает бесконечно (требуется `--daemon`). |
| `--log-file PATH` | `stdout` | Путь к файлу лога. По умолчанию вывод в консоль. |
| `--daemon` | — | Запуск в режиме демона (бесконечный цикл). Автоматически устанавливает `--samples 0`. |
| `--steam-path PATH` | автоопределение | Путь к каталогу установки Steam (вместо автоматического поиска). |

### Примеры

**Базовый запуск (6 выборок с интервалом 1 мин = 5 мин):**
```bash
steam-monitor
```

**Запуск с кастомным путём к Steam:**
```bash
steam-monitor --steam-path "/mnt/games/Steam"
```

**Запуск в фоне (до остановки вручную):**
```bash
steam-monitor --daemon
```

**Логирование в файл:**
```bash
steam-monitor --log-file steam_monitor.log
```

## Поддерживаемые платформы

- **Windows** (через реестр)
- **Linux** (через `~/.steam/steam`)
- **macOS** (через `~/Library/Application Support/Steam`)

## Выходные данные

Пример строки лога:
```
2026-02-04 18:00:00 - INFO - Status: DOWNLOADING, Game: Half-Life: Alyx, Speed: 12.45 MB/s
```

## Требования

- Python 3.10+
- Пакет `watchdog`