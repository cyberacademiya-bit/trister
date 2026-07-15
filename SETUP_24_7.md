# 🤖 Запуск бота 24/7 (автономно, бесплатно)

Схема: **GitHub Actions** гоняет бота раз в день → обновляет данные →
**Vercel** сам передеплоит дашборд. Мак может быть выключен.

Локальный git уже готов (я закоммитил). Осталось 3 шага 👇

---

## Шаг 1 — создать репозиторий на GitHub и залить

1. Зайди на **https://github.com/new**
2. Имя: `trister` · сделай **Private** (приватный) · **не** добавляй README/gitignore
3. Нажми **Create repository**
4. В терминале (замени `ТВОЙ_ЛОГИН`):

```bash
cd "/Users/aim/Проекты/Тристер"
git remote add origin https://github.com/ТВОЙ_ЛОГИН/trister.git
git push -u origin main
```
*(если попросит логин — введи логин GitHub и **токен** вместо пароля: github.com → Settings → Developer settings → Personal access tokens)*

---

## Шаг 2 — добавить ключи в секреты (НЕ в код!)

Репо → **Settings → Secrets and variables → Actions → New repository secret**.
Создай **6 секретов** (значения возьми из файла `.env` в папке проекта):

| Имя секрета | Откуда значение |
|---|---|
| `BINANCE_API_KEY` | из .env |
| `BINANCE_API_SECRET` | из .env |
| `FUTURES_KEY` | из .env |
| `FUTURES_SECRET` | из .env |
| `ALPACA_KEY` | из .env |
| `ALPACA_SECRET` | из .env |

*(Ключи демо/testnet — риск низкий. В сам код они не попадают, `.env` в git исключён.)*

После этого во вкладке **Actions** можно нажать **Run workflow** — проверить прямо сейчас.
Дальше бот запускается **сам каждый день в 14:00 UTC**.

---

## Шаг 3 — подключить Vercel (дашборд 24/7)

1. Зайди на **https://vercel.com** → **Add New → Project**
2. **Import** свой GitHub-репозиторий `trister`
3. В настройках проекта: **Root Directory** → указать **`site`**
4. **Deploy**

Готово! Получишь ссылку `trister-xxx.vercel.app` — открывается **с любого устройства**.
Каждый день, когда бот обновит данные, Vercel **сам передеплоит** — дашборд всегда свежий.

---

## Итог

```
GitHub Actions (бот) ──ежедневно──► торгует на всех демо
        │
        └──► коммит данных ──► Vercel ──► дашборд онлайн 24/7
```

Всё бесплатно, автономно, Мак не нужен. 🚀
