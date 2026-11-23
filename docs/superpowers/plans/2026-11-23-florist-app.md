# Приложение «Флористический центр» — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Настольное приложение на PyQt5 и чистом SQL (psycopg2) для БД «Флористический центр» из 13 таблиц: справочники, книга рецептов, заказы, списания, заявки на закупку и 7 отчётов задания.

**Architecture:**
- Весь SQL лежит в `app/sql.py` в виде констант.
- `app/db.py` отвечает за одно соединение, чтение, запись в транзакции и понятные тексты ошибок.
- Экраны лежат в `app/ui/`. Шесть простых справочников обслуживает один общий класс `DirectoryTab`, который настраивается словарями.
- Логика, которую можно проверить без окон (сохранение заказа, предварительная цена, проверка заказа), вынесена в функции модулей `ui/`, и её проверяют тесты pytest на настоящей БД в Docker.

**Tech Stack:** Python 3.12, PyQt5, psycopg2-binary, PostgreSQL 16 (Docker `postgres:16`, порт 5433), pytest (только для тестов).

**Spec:** [developing_plan.md](../../../developing_plan.md). Исполнитель читает его вместе с этим планом. Тексты схемы, функций, триггеров и 7 запросов взяты из пояснительной записки (листинги 3.1–3.13) и приведены в задаче 1 как точные требования.

## Global Constraints

- Только нативный SQL через psycopg2. Никакого ORM.
- Весь SQL — константы в `app/sql.py`. В других модулях `app/` SQL-текста нет.
- Только параметризованные запросы с `%s`. Никаких f-строк, `.format`, `%`-форматирования и конкатенации значений в SQL.
- Ни один `INSERT` приложения не передаёт `id`. Новый ключ получаем через `RETURNING id`. В тестовых данных ссылки на только что вставленную строку берутся через `currval('посл_…')` или подзапрос по названию.
- Остаток, цены в составе и позициях, заявки и пополнение склада не считаются в Python. Это делают `тр_склад`, `проверить_запас`, `сформировать_заявки`, `тр_поставка`.
- Рекомендуемая цена сохранённого букета берётся только через `рекоменд_цена(id)`.
- Схема — ровно листинги 3.1–3.6, кроме `CREATE EXTENSION pg_cron` и `cron.schedule` (они уходят в `database/pg_cron.sql`). Схему не менять.
- Параметры подключения хранятся в `app/config.ini`, секция `[database]`: `host=localhost`, `port=5433`, `dbname=florist`, `user=postgres`, `password=flowers`.
- Допустимые значения CHECK (выпадающие списки):
  - тип: `срезанный`, `горшечный`;
  - должность: `флорист`, `курьер`;
  - сложность: `простой`, `средний`, `сложный`;
  - способ оплаты: `наличные`, `карта`, `перевод`;
  - причина: `увядание`, `брак`, `повреждение`;
  - статус: `новая`, `выполнена`, `отменена`.
- Пустое необязательное текстовое поле сохраняется как `NULL`, а не `''`.
- Ошибки БД пользователь видит в `QMessageBox` с текстом `db.error_text(e)`. После ошибки соединение снова рабочее.
- Код простой: никаких слоёв, паттернов и фреймворков сверх описанного в спецификации.
- Работа идёт в ветке `feature/app`. Коммит делается после каждой задачи и только если пользователь разрешил коммиты.

## Review Focus

1. **Пустой телефон у двух клиентов.** Оба должны сохраниться. Если писать `''` вместо NULL, сработает UNIQUE. Тест в задаче 3.
2. **Одно растение дважды** в составе букета или в списке отдельных растений. Ожидается понятное сообщение до отправки в БД, а не ошибка первичного ключа посреди транзакции. Тест в задаче 5.
3. **Самовывоз при заполненных полях доставки.** Если курьер не выбран, адрес, получатель, телефон получателя и время доставки сохраняются как NULL. Тест в задаче 5.
4. **Операция после ошибки.** После любой неудачной записи следующее чтение и следующая запись проходят, то есть соединение не остаётся в состоянии «transaction aborted». Тест в задаче 2.
5. **БД недоступна при запуске.** Показывается понятное сообщение с host/port/dbname, без трассировки. `error_text` работает и для ошибок без `pgcode`. Тест в задаче 2.

---

## Структура файлов

```
database/флористический_центр.sql   схема (листинги 3.1–3.6 без pg_cron)
database/pg_cron.sql                 CREATE EXTENSION pg_cron + cron.schedule (листинг 3.5, хвост)
database/тестовые_данные.sql         тестовые данные, даты относительно now()
database/запросы.sql                 листинги 3.7–3.13 дословно, перед каждым строка "-- Запрос N"
app/config.ini                       параметры подключения
app/requirements.txt                 psycopg2-binary, PyQt5
app/db.py                            соединение, fetch/fetch_value/execute/transaction, error_text
app/sql.py                           все SQL-константы
app/main.py                          QApplication, подключение, MainWindow с 10 вкладками
app/ui/__init__.py                   пустой
app/ui/common.py                     общие помощники Qt: таблица, сообщения, формат
app/ui/directories.py                DirectoryTab, RecordDialog, DIRECTORIES (6 справочников)
app/ui/templates.py                  TemplatesTab
app/ui/orders.py                     save_order, price_preview, validate_order, OrdersTab, OrderDialog, BouquetDialog, OrderViewDialog
app/ui/purchases.py                  PurchasesTab
app/ui/reports.py                    REPORTS, ReportsTab
tests/conftest.py                    создание florist_test из скриптов, подключение db
tests/test_database.py               схема и тестовые данные
tests/test_db.py                     db.py
tests/test_directories.py            CRUD 6 справочников
tests/test_templates.py              книга рецептов
tests/test_orders.py                 логика заказа
tests/test_purchases.py              заявки
tests/test_reports.py                7 отчётов против запросы.sql
tests/test_ui_smoke.py               MainWindow в offscreen, refresh всех вкладок
```

`app/ui/common.py` — небольшое отступление от спецификации **[моё решение]**: без него помощники для таблиц и сообщений повторялись бы в пяти модулях.

Скрипта `check.py` из спецификации не будет. Его роль выполняют тесты `tests/` под pytest, а проверяются ими те же функции `db.py` и SQL из `sql.py`.

Приложение запускается командой `python app/main.py`, поэтому модули импортируются как `import db`, `import sql`, `from ui import …`. `tests/conftest.py` добавляет `app/` в `sys.path`.

---

### Задача 1: SQL-скрипты, тестовая БД и окружение

**Files:**
- Create: `database/флористический_центр.sql`, `database/pg_cron.sql`, `database/тестовые_данные.sql`, `database/запросы.sql`
- Create: `tests/conftest.py`, `tests/test_database.py`, `app/requirements.txt`, `.gitignore` (`.venv/`, `__pycache__/`, `.idea/`, `.pytest_cache/`)

**Interfaces:**
- Produces:
  - БД `florist` (для приложения), в которой загружены схема и данные.
  - В `tests/conftest.py`:
    - `TEST_PARAMS: dict` — параметры подключения к `florist_test` (`app/config.ini`, в котором `dbname` заменён на `florist_test`);
    - сессионная фикстура `test_db`, которая создаёт `florist_test` из скриптов;
    - фикстура `cur` — курсор psycopg2 к `florist_test` с autocommit;
    - функция `query_blocks() -> dict[int, str]`.
- Тестовые данные гарантируют сущности, на которые опираются тесты:
  - категории «Розы» (коэф. 2.00) и «Зелень» (1.50);
  - растения «Роза красная» (срезанный, Розы, 95.00) и «Эвкалипт» (срезанный, Зелень, 60.00), у обоих остаток после загрузки ≥ 100;
  - флорист «Иванова Анна Сергеевна», курьер «Петров Игорь Олегович»;
  - клиент «Мария» с телефоном `+79160000001`;
  - шаблон «Классика» флористки Ивановой: Роза красная × 7, Эвкалипт × 3;
  - шаблон «Весенний» (любой флорист), по которому продан хотя бы один букет. Его удаляет тест задачи 4, поэтому другие тесты на этот шаблон не опираются.

- [ ] **Step 1: Ветка и окружение**

Run:
```
git checkout -b feature/app
python -m venv .venv
.venv\Scripts\python -m pip install psycopg2-binary PyQt5 pytest
docker run --name flowers-pg -e POSTGRES_PASSWORD=flowers -p 5433:5432 -d postgres:16
docker exec flowers-pg psql -U postgres -c "select version()"
```
Expected: в выводе есть `PostgreSQL 16`.

- [ ] **Step 2: `флористический_центр.sql`**

Перенести дословно листинги 3.1 (последовательности, 13 таблиц, OWNED BY), 3.2 (`рекоменд_цена`), 3.4 (`проверить_запас`), 3.3 (`тр_склад` и три триггера), начало 3.5 (`сформировать_заявки`) и 3.6 (`тр_поставка`, триггер `поставка_заявки`).

`проверить_запас` нужно создать раньше `тр_склад`. PL/pgSQL проверяет вызов только во время выполнения, поэтому порядок не критичен, но так скрипт читается сверху вниз.

`CREATE EXTENSION pg_cron` и `cron.schedule` вынести в `pg_cron.sql`.

- [ ] **Step 3: `запросы.sql`**

Листинги 3.7–3.13 дословно. Перед каждым запросом строка `-- Запрос N`, где N от 1 до 7, каждый запрос заканчивается `;`.

- [ ] **Step 4: Тест схемы, падающий**

`tests/conftest.py` при старте сессии:
1. подключается к БД `postgres` с `autocommit`;
2. выполняет `DROP DATABASE IF EXISTS florist_test` и `CREATE DATABASE florist_test ENCODING 'UTF8' TEMPLATE template0`;
3. выполняет файлы целиком (`cursor.execute(text)` без параметров, файл читается в `utf-8`) в порядке: `флористический_центр.sql`, `тестовые_данные.sql`.

`tests/test_database.py`:
```python
def test_13_tables(cur):
    cur.execute("select count(*) from information_schema.tables where table_schema='public'")
    assert cur.fetchone()[0] == 13

def test_10_sequences(cur):
    cur.execute("select count(*) from information_schema.sequences where sequence_name like 'посл_%'")
    assert cur.fetchone()[0] == 10

def test_recommended_price_example(cur):
    # пример из раздела 3.2: 7 × 95 × 2,00 + 3 × 60 × 1,50 = 1600
    cur.execute("""select sum(сш.количество * р.закупочная_цена * к.коэф_наценки)
                   from состав_шаблона сш join шаблоны ш on ш.id = сш.шаблон_id
                   join растения р on р.id = сш.растение_id join категории к on к.id = р.категория_id
                   where ш.название = 'Классика'""")
    assert cur.fetchone()[0] == Decimal("1600.00")

def test_every_report_has_rows(cur):          # для каждого из 7 блоков запросы.sql
    ...                                         # (для запроса 6: xml содержит '<категория>')
    assert rows                                 # не пусто

def test_q5_has_12_months_with_a_zero(cur):   # блок "-- Запрос 5"
    assert len(rows) == 12 and any(r[1] == 0 for r in rows)

def test_q4_at_least_3_low_stock(cur):        # блок "-- Запрос 4"
    assert len(rows) >= 3

def test_auto_purchase_requests_exist(cur):
    cur.execute("select count(*) from заявки_на_закупку where статус = 'новая'")
    assert cur.fetchone()[0] >= 1

def test_all_bouquet_kinds(cur):
    cur.execute("select count(distinct сложность), count(*) filter (where шаблон_id is null), "
                "count(*) filter (where шаблон_id is not null) from букеты")
    kinds, individual, by_template = cur.fetchone()
    assert kinds == 3 and individual > 0 and by_template > 0
```
Фикстура `cur` — курсор к `florist_test`. Вспомогательная функция `query_blocks()` в `conftest.py` делит `запросы.sql` по строкам `-- Запрос N` и возвращает `{N: sql}`.

Run: `.venv\Scripts\python -m pytest tests/test_database.py -v`
Expected: FAIL. Файла тестовых данных ещё нет.

- [ ] **Step 5: `тестовые_данные.sql`**

Состав данных — раздел 7 спецификации плюс сущности из блока Interfaces выше:
- 5–6 категорий, 3–4 поставщика с разными сроками поставки, около 20 растений;
- 3 флориста, 2 курьера, около 8 клиентов (у 2 телефона нет);
- 2–3 шаблона на флориста;
- около 60 заказов, около 10 списаний.

Правила:
- **Все даты относительно `now()`.** Используются выражения вида `date_trunc('year', now()) - interval '1 year' + interval '…'` и `date_trunc('quarter', now()) - interval '2 months' + …`.
- **Покрытие по периодам:**
  - прошлый год — 10–11 месяцев из 12;
  - прошлый квартал;
  - текущий год.
- **Ссылки на только что вставленные строки** берутся через `currval('посл_заказы')` и `currval('посл_букеты')`. Ссылки на справочники — подзапросами по названию или ФИО.
- **Цены не указываются** в `состав_букета.закупочная_цена` и `растения_в_заказе.цена`: их подставит триггер.
- **Остатки:**
  - начальные остатки задаются так, чтобы продажи прошли;
  - 3–4 растения в итоге оказываются ниже `мин_остаток`;
  - у «Розы красной» и «Эвкалипта» после загрузки остаётся ≥ 100.

Run: `docker exec flowers-pg createdb -U postgres -E UTF8 -T template0 florist`, затем скопировать папку (`docker cp database flowers-pg:/database`) и выполнить оба скрипта через `psql -v ON_ERROR_STOP=1 -f`.
Expected: оба скрипта проходят без `ERROR`.

- [ ] **Step 6: Тесты проходят**

Run: `.venv\Scripts\python -m pytest tests/test_database.py -v`
Expected: PASS.

- [ ] **Step 7: Сверка с psql**

Run: `docker exec flowers-pg psql -U postgres -d florist -f /database/запросы.sql`
Expected: 7 непустых результатов. Сохранить вывод в `docs/проверка/запросы_psql.txt` для отчёта о проверке.

- [ ] **Step 8: Commit** — `database/`, `tests/`, `app/requirements.txt`, `.gitignore`: «Скрипты БД, тестовые данные и тесты схемы».

---

### Задача 2: `db.py`, `config.ini`, каркас `main.py`

**Files:**
- Create: `app/config.ini`, `app/db.py`, `app/sql.py` (пока пустой, с докстрингом), `app/main.py`, `app/ui/__init__.py`, `app/ui/common.py`
- Test: `tests/test_db.py`, `tests/test_ui_smoke.py`
- Modify: `tests/conftest.py`:
  - сессионная autouse-фикстура вызывает `db.connect(TEST_PARAMS)` после `test_db`;
  - сессионная фикстура `qapp` выставляет `QT_QPA_PLATFORM=offscreen` и создаёт единственный `QApplication`. Её используют все тесты с виджетами.

**Interfaces:**
- Produces (`app/db.py`, модульная переменная `conn`):
  - `read_config(path: str = <app/config.ini>) -> dict` — секция `[database]` в виде dict для `psycopg2.connect`.
  - `connect(params: dict | None = None) -> None` — при `None` берёт `read_config()`.
  - `fetch(sql: str, params: tuple | list | None = None) -> tuple[list[str], list[tuple]]` — возвращает названия колонок и строки; после чтения выполняет `conn.rollback()`.
  - `fetch_value(sql, params=None)` — первая колонка первой строки или `None`.
  - `execute(sql, params=None)` — одна команда в `with conn:`. Если команда вернула строку, возвращает её первую колонку, иначе `None`.
  - `transaction()` — контекстный менеджер, отдаёт курсор внутри `with conn:` (COMMIT при выходе, ROLLBACK при исключении).
  - `error_text(e: Exception) -> str` — таблица из спецификации 6.1. Если `pgcode` нет (OperationalError и т. п.), возвращает `str(e).strip()`.
- Produces (`app/ui/common.py`):
  - `fill_table(table: QTableWidget, columns: list[str], rows: list[tuple], hidden: int = 1) -> None` — первые `hidden` колонок скрыты (в них id). Значения выводятся через `fmt`.
  - `selected_id(table: QTableWidget) -> int | None` — значение скрытой колонки 0 у выделенной строки.
  - `fmt(value) -> str` — `None` превращается в `''`, `Decimal` выводится с 2 знаками, `datetime` как `ДД.ММ.ГГГГ ЧЧ:ММ`, `date` как `ДД.ММ.ГГГГ`.
  - `show_error(parent, e: Exception) -> None` — `QMessageBox.warning` с текстом `db.error_text(e)`.
  - `confirm(parent, text: str) -> bool`.
- Produces (`app/main.py`):
  - `MainWindow(QMainWindow)` с `QTabWidget` `self.tabs`. При смене вкладки вызывается её `refresh()`.
  - `main()`: если подключиться не удалось, показывает `QMessageBox.critical` с текстом «Не удалось подключиться к БД host:port/dbname» и `error_text` и выходит с кодом 1.
  - Каждая вкладка проекта — `QWidget` с методом `refresh(self) -> None`.

- [ ] **Step 1: Тесты `db`, падающие**

```python
def test_fetch_returns_columns_and_rows():
    cols, rows = db.fetch("select название, коэф_наценки from категории where название = %s", ("Розы",))
    assert cols == ["название", "коэф_наценки"] and rows == [("Розы", Decimal("2.00"))]

def test_execute_returning_id_uses_sequence():
    new_id = db.execute("insert into категории (название, коэф_наценки) values (%s, %s) returning id", ("Тест-кат", 1.2))
    assert isinstance(new_id, int) and db.fetch_value("select currval('посл_категории')") == new_id
    db.execute("delete from категории where id = %s", (new_id,))

def test_transaction_rolls_back_everything():
    before = db.fetch_value("select count(*) from категории")
    with pytest.raises(psycopg2.Error):
        with db.transaction() as cur:
            cur.execute("insert into категории (название, коэф_наценки) values ('X1', 1.5)")
            cur.execute("insert into категории (название, коэф_наценки) values ('X2', 0.5)")  # CHECK
    assert db.fetch_value("select count(*) from категории") == before

def test_connection_usable_after_error():                       # Review Focus 4
    with pytest.raises(psycopg2.Error):
        db.execute("insert into категории (название, коэф_наценки) values ('Розы', 2)")
    assert db.fetch_value("select 1") == 1
    new_id = db.execute("insert into категории (название, коэф_наценки) values ('X3', 1.1) returning id")
    db.execute("delete from категории where id = %s", (new_id,))

@pytest.mark.parametrize("sql_text, fragment", [
    ("delete from категории where название = 'Розы'", "используется"),       # 23503
    ("insert into категории (название, коэф_наценки) values ('Розы', 2)", "уже есть"),  # 23505
    ("insert into категории (название, коэф_наценки) values ('Y', 0.5)", "Недопустимое"),  # 23514
    ("insert into категории (название, коэф_наценки) values (null, 2)", "Не заполнено"),   # 23502
])
def test_error_text_by_code(sql_text, fragment):
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql_text)
    assert fragment in db.error_text(exc.value)

def test_error_text_trigger_message():   # P0001: продать больше остатка через списание
    with pytest.raises(psycopg2.Error) as exc:
        db.execute("insert into списания (растение_id, количество, причина) "
                   "select id, остаток + 1, 'брак' from растения where название = 'Роза красная'")
    assert db.error_text(exc.value).startswith("Недостаточно «Роза красная» на складе")

def test_error_text_without_pgcode():                            # Review Focus 5
    with pytest.raises(psycopg2.OperationalError) as exc:
        psycopg2.connect(host="localhost", port=1, dbname="x", user="x", password="x", connect_timeout=2)
    assert db.error_text(exc.value)

def test_config_has_connection_keys():
    assert set(db.read_config()) == {"host", "port", "dbname", "user", "password"}
```
`tests/test_ui_smoke.py` с фикстурой `qapp` создаёт `MainWindow()` и проверяет `tabs.count() == 10` и что для каждой вкладки `refresh()` проходит без исключения. На этой задаче вкладки — заглушки `QWidget` с пустым `refresh`, названия по спецификации 6.8. В задачах 3–8 заглушки заменяются настоящими экранами.

Run: `.venv\Scripts\python -m pytest tests/test_db.py tests/test_ui_smoke.py -v`
Expected: FAIL (`ModuleNotFoundError: db`).

- [ ] **Step 2: Реализовать** `config.ini`, `db.py`, `ui/common.py`, `main.py` по интерфейсам выше. Тексты `error_text` берутся из спецификации 6.1. Имя таблицы для 23503 — `e.diag.table_name`, имя поля для 23505/23502 — `e.diag.column_name` или `e.diag.constraint_name`.

- [ ] **Step 3: Тесты проходят**

Run: `.venv\Scripts\python -m pytest tests -v`
Expected: PASS.

- [ ] **Step 4: Ручной запуск**

Run: `.venv\Scripts\python app/main.py`
Expected: открылось окно с 10 вкладками. При неверном `port` в `config.ini` вместо окна появляется сообщение об ошибке подключения.

- [ ] **Step 5: Commit** — «db.py, конфиг и каркас главного окна».

---

### Задача 3: Справочники (6 вкладок)

**Files:**
- Modify: `app/sql.py`, `app/main.py` (6 заглушек заменяются на `DirectoryTab`)
- Create: `app/ui/directories.py`
- Test: `tests/test_directories.py`

**Interfaces:**
- Consumes: `db.*`, `ui.common.*`.
- Produces (`app/sql.py`):
  - для ENTITY ∈ {`CATEGORY`, `SUPPLIER`, `PLANT`, `EMPLOYEE`, `CLIENT`, `WRITEOFF`} константы `ENTITY_LIST`, `ENTITY_GET`, `ENTITY_INSERT`, `ENTITY_UPDATE`, `ENTITY_DELETE`;
  - `ENTITY_LIST` — первая колонка `id`, далее колонки для показа с русскими заголовками через `AS`;
  - `ENTITY_GET` (по `%s` = id) — поля формы в порядке `fields`;
  - `ENTITY_INSERT` — `%s` в порядке `fields`, `RETURNING id`;
  - `ENTITY_UPDATE` — `%s` в порядке `fields`, затем `id`;
  - `ENTITY_DELETE` — `%s` = id;
  - справочники для выпадающих списков, все возвращают `(id, подпись)`: `CATEGORIES_LOOKUP`, `SUPPLIERS_LOOKUP`, `PLANTS_LOOKUP` (подпись «название (ост. N)»), `FLORISTS_LOOKUP`, `COURIERS_LOOKUP`, `CLIENTS_LOOKUP` (подпись «имя — телефон» или просто «имя»).
- Produces (`app/ui/directories.py`):
  - `DIRECTORIES: list[dict]`, ключи словаря:
    - `title: str`;
    - `list`, `get`, `insert`, `update`, `delete: str`;
    - `fields: list[tuple[str, str, object, bool]]` — `(подпись, вид, доп, обязательное)`. `вид` ∈ {`text`, `int`, `money`, `choice`, `ref`}. `доп` зависит от вида: для `choice` — список значений, для `ref` — SQL справочника, для `int` — `(min, max)`, для остальных — `None`;
    - `highlight_col: int | None` — индекс скрытой булевой колонки LIST, по которой строка подсвечивается;
    - `delete_question: str`.
  - `RecordDialog(QDialog)`: `__init__(parent, config, values: tuple | None)`, метод `values() -> tuple`. Пустой `text` превращается в `None`.
  - `DirectoryTab(QWidget)`: `__init__(config)`, `refresh()`, кнопки «Добавить», «Изменить», «Удалить», «Обновить». Двойной щелчок открывает «Изменить».
  - `main.py` ставит вкладки справочников на их места по порядку из спецификации 6.8. «Списания» — восьмая вкладка, после «Заказов».

Поля справочников — таблица в спецификации 6.3:
- у «Растений» LIST содержит в конце скрытую колонку `остаток < мин_остаток`;
- у «Списаний» LIST: дата, растение, количество, причина; в форме: растение (`ref` на `PLANTS_LOOKUP`), количество, причина;
- `delete_question` у «Списаний»: «Отменить списание? Растения вернутся на склад».

- [ ] **Step 1: Тесты, падающие**

```python
SAMPLES = {  # title -> (значения для insert, значения для update)
    "Категории":  (("Тест-кат", 1.30), ("Тест-кат-2", 1.40)),
    "Поставщики": (("Тест-пост", "+70000000000", 2), ("Тест-пост-2", None, 3)),
    "Растения":   (("Тест-растение", "горшечный", <id Розы>, <id поставщика>, 100.00, 10, 2),
                   ("Тест-растение", "горшечный", <id Розы>, <id поставщика>, 110.00, 20, 2)),
    "Сотрудники": (("Тестов Т.Т.", "курьер", None), ("Тестов Т.Т.", "флорист", "+70000000001")),
    "Клиенты":    (("Тест-клиент", None, None), ("Тест-клиент", "+70000000002", "t@t.ru")),
    "Списания":   ((<id Эвкалипта>, 2, "брак"), (<id Эвкалипта>, 3, "увядание")),
}

@pytest.mark.parametrize("cfg", DIRECTORIES, ids=lambda c: c["title"])
def test_crud_roundtrip(cfg):
    ins, upd = SAMPLES[cfg["title"]]
    new_id = db.execute(cfg["insert"], ins)
    assert normalize(db.fetch(cfg["get"], (new_id,))[1][0]) == ins
    db.execute(cfg["update"], upd + (new_id,))
    assert normalize(db.fetch(cfg["get"], (new_id,))[1][0]) == upd
    assert any(r[0] == new_id for r in db.fetch(cfg["list"])[1])
    db.execute(cfg["delete"], (new_id,))
    assert db.fetch(cfg["get"], (new_id,))[1] == []

def test_writeoff_moves_stock():           # сценарий 11
    # остаток Эвкалипта: до − 2 после insert; после update на 3: до − 3; после delete: до

def test_writeoff_over_stock_rejected():   # P0001, остаток не изменился

def test_two_clients_without_phone():      # Review Focus 1
    a = db.execute(CLIENT_INSERT, ("Без телефона 1", None, None)); b = db.execute(CLIENT_INSERT, ("Без телефона 2", None, None))
    assert a != b

@pytest.mark.parametrize("delete_sql, name_sql", [...5 справочников: Розы, поставщик, Роза красная, Иванова, Мария])
def test_delete_used_record_gives_clear_error(delete_sql, name_sql):   # сценарий 3
    assert "используется" in db.error_text(exc.value)

def test_plants_list_flags_low_stock():
    cols, rows = db.fetch(sql.PLANT_LIST)
    assert sum(1 for r in rows if r[-1]) >= 3

def test_lookups_filter_roles():
    assert all("Петров" not in label for _, label in db.fetch(sql.FLORISTS_LOOKUP)[1])
    assert all("Иванова" not in label for _, label in db.fetch(sql.COURIERS_LOOKUP)[1])

def test_record_dialog_empty_text_is_none(qapp):   # Review Focus 1, со стороны формы
    dlg = RecordDialog(None, cfg_clients, None); <ввести имя, телефон оставить пустым>
    assert dlg.values()[1] is None
```
`normalize` приводит `Decimal` к `float`. Фикстура `qapp` — из задачи 2.

Run: `.venv\Scripts\python -m pytest tests/test_directories.py -v` → FAIL.

- [ ] **Step 2: SQL-константы** в `app/sql.py` по интерфейсу.
- [ ] **Step 3: `directories.py`** — `RecordDialog`, `DirectoryTab`, `DIRECTORIES`.
  - Ошибки ловятся через `except psycopg2.Error as e: show_error(self, e)`.
  - Если в форме не заполнено обязательное поле, показывается сообщение «Заполните поле …» и запрос в БД не отправляется.
  - Подсветка строк: фон `#ffd6d6`.
- [ ] **Step 4: `main.py`** — 6 заглушек заменяются на `DirectoryTab(cfg)` из `DIRECTORIES`.
- [ ] **Step 5:** Run `.venv\Scripts\python -m pytest tests -v` → PASS.
- [ ] **Step 6: Ручная проверка.**
  - Добавить, изменить и удалить растение. Категория и поставщик выбираются названием.
  - Удалить категорию «Розы» — должно появиться сообщение «используется».
  - Строки «Растений» с низким остатком подсвечены.
- [ ] **Step 7: Commit** — «Справочники: CRUD шести таблиц».

---

### Задача 4: Книга рецептов

**Files:**
- Modify: `app/sql.py`, `app/main.py`
- Create: `app/ui/templates.py`
- Test: `tests/test_templates.py`

**Interfaces:**
- Produces (`sql.py`):
  - `TEMPLATES_BY_FLORIST` (`%s` = флорист_id) возвращает `(id, название)`;
  - `TEMPLATE_INSERT` (флорист_id, название) `RETURNING id`; `TEMPLATE_RENAME` (название, id); `TEMPLATE_DELETE` (id);
  - `TEMPLATE_ITEMS` (`%s` = шаблон_id) возвращает `(растение_id, растение, количество)`;
  - `TEMPLATE_ITEM_INSERT` (шаблон_id, растение_id, количество); `TEMPLATE_ITEM_UPDATE` (количество, шаблон_id, растение_id); `TEMPLATE_ITEM_DELETE` (шаблон_id, растение_id).
- Produces (`ui/templates.py`): `TemplatesTab(QWidget)` с `refresh()`, раскладка — спецификация 6.4. Количество вводится через `QInputDialog.getInt(min=1)`, растение и название — через простой диалог.

- [ ] **Step 1: Тесты, падающие**
  - `test_template_crud`: создать шаблон у Ивановой, он появляется в `TEMPLATES_BY_FLORIST`; переименовать; добавить 2 позиции; изменить количество; удалить позицию; удалить шаблон. Состав удаляется каскадно: `TEMPLATE_ITEMS` пуст.
  - `test_duplicate_item_rejected`: вторая вставка того же растения даёт ошибку `23505`, `error_text` содержит «уже есть».
  - `test_deleting_template_keeps_bouquets`: запомнить id букетов шаблона «Весенний» и выполнить `TEMPLATE_DELETE`. Общее `count(*)` букетов не изменилось, у запомненных букетов `шаблон_id IS NULL`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** SQL-константы и `TemplatesTab`. Удаление шаблона подтверждается текстом «Проданные по шаблону букеты останутся и станут индивидуальными. Удалить?».
- [ ] **Step 4:** Run `pytest tests -v` → PASS.
- [ ] **Step 5: Ручная проверка** — сценарий 5 спецификации.
- [ ] **Step 6: Commit** — «Книга рецептов».

---

### Задача 5: Логика заказа (без окон)

**Files:**
- Modify: `app/sql.py`
- Create: `app/ui/orders.py` (в этой задаче только функции)
- Test: `tests/test_orders.py`

**Interfaces:**
- Produces (`sql.py`):
  - `ORDER_INSERT` (клиент_id, флорист_id, способ_оплаты, курьер_id, адрес_доставки, время_доставки, получатель, телефон_получателя) `RETURNING id`;
  - `BOUQUET_INSERT` (заказ_id, шаблон_id, сложность, время_сборки, цена_продажи) `RETURNING id`;
  - `BOUQUET_ITEM_INSERT` (букет_id, растение_id, количество) — без цены;
  - `ORDER_PLANT_INSERT` (заказ_id, растение_id, количество) — без цены;
  - `ORDER_DELETE` (id);
  - `PRICE_PREVIEW` (`%s::int[]` растения, `%s::int[]` количества) — текст в спецификации 6.2;
  - `RECOMMENDED_PRICE` — `SELECT рекоменд_цена(%s)`.
- Produces (`ui/orders.py`), где `Order` — это dict:
  ```
  {"клиент_id": int, "флорист_id": int, "способ_оплаты": str, "курьер_id": int | None,
   "адрес_доставки": str | None, "время_доставки": datetime | None,
   "получатель": str | None, "телефон_получателя": str | None,
   "букеты": [{"шаблон_id": int | None, "сложность": str, "время_сборки": int,
              "цена_продажи": Decimal, "состав": [(растение_id, количество), ...]}],
   "растения": [(растение_id, количество), ...]}
  ```
  - `validate_order(order: dict) -> str | None` — текст первой найденной ошибки или `None`.
  - `save_order(order: dict) -> int` — одна `db.transaction()`, порядок вставок — спецификация 6.5. Если `курьер_id is None`, четыре поля доставки пишутся как `None`. Исключения psycopg2 пробрасываются наружу.
  - `price_preview(items: list[tuple[int, int]]) -> Decimal` — пустой список даёт `Decimal("0")`.

Тексты `validate_order`, проверка идёт в этом порядке:

| Условие | Текст |
| --- | --- |
| нет клиента | «Выберите клиента» |
| нет флориста | «Выберите флориста» |
| курьер выбран, адрес пуст | «Укажите адрес доставки» |
| нет ни букетов, ни растений | «Добавьте в заказ букет или растение» |
| в букете N нет позиций | «В букете N нет растений» |
| в букете N растение повторяется | «В букете N растение указано дважды» |
| в отдельных растениях есть повтор | «Растение указано в заказе дважды» |

- [ ] **Step 1: Тесты, падающие**

```python
def test_price_preview_matches_example():
    assert orders.price_preview([(rose, 7), (eucalyptus, 3)]) == Decimal("1600.00")
    assert orders.price_preview([]) == Decimal("0")

def test_save_order_decreases_stock_and_delete_restores():          # сценарии 6, 8
    before = stock(rose), stock(eucalyptus), stock(potted)
    oid = orders.save_order(order(bouquets=[template_bouquet(классика, rose=5, eucalyptus=3),   # изменённый состав
                                             individual(rose=2)],
                                   plants=[(potted, 1)]))
    assert stock(rose) == before[0] - 7 and stock(eucalyptus) == before[1] - 3 and stock(potted) == before[2] - 1
    assert db.fetch_value("select count(*) from состав_букета сб join букеты б on б.id = сб.букет_id "
                          "where б.заказ_id = %s and сб.закупочная_цена is null", (oid,)) == 0
    assert db.fetch_value("select цена from растения_в_заказе where заказ_id = %s", (oid,)) is not None
    db.execute(sql.ORDER_DELETE, (oid,))
    assert (stock(rose), stock(eucalyptus), stock(potted)) == before

def test_preview_equals_function_after_save():                       # сценарий 7
    items = [(rose, 7), (eucalyptus, 3)]
    oid = orders.save_order(order(bouquets=[individual_items(items)]))
    bid = db.fetch_value("select id from букеты where заказ_id = %s", (oid,))
    assert db.fetch_value(sql.RECOMMENDED_PRICE, (bid,)) == orders.price_preview(items)

def test_shortage_rolls_back_everything():                           # сценарий 9
    orders_before, bouquets_before, stock_before = count("заказы"), count("букеты"), stock(rose)
    with pytest.raises(psycopg2.Error) as exc:
        orders.save_order(order(bouquets=[individual(eucalyptus=1)], plants=[(rose, stock_before + 1)]))
    assert "Недостаточно" in db.error_text(exc.value)
    assert (count("заказы"), count("букеты"), stock(rose)) == (orders_before, bouquets_before, stock_before)

def test_pickup_clears_delivery_fields():                            # Review Focus 3
    oid = orders.save_order(order(courier=None, address="ул. Ленина, 1", recipient="Оля"))
    assert db.fetch("select адрес_доставки, получатель, телефон_получателя, время_доставки "
                    "from заказы where id = %s", (oid,))[1][0] == (None, None, None, None)

@pytest.mark.parametrize("change, message", [
    ({"клиент_id": None}, "Выберите клиента"),
    ({"курьер_id": <курьер>, "адрес_доставки": None}, "Укажите адрес доставки"),
    ({"букеты": [], "растения": []}, "Добавьте в заказ букет или растение"),
    ({"букеты": [bouquet(состав=[])]}, "В букете 1 нет растений"),
    ({"букеты": [bouquet(состав=[(rose, 1), (rose, 2)])]}, "В букете 1 растение указано дважды"),  # Review Focus 2
    ({"растения": [(rose, 1), (rose, 1)]}, "Растение указано в заказе дважды"),
])
def test_validate_order(change, message):
    assert orders.validate_order({**valid_order(), **change}) == message
```
Помощники `order(...)`, `individual(...)`, `stock(...)`, `count(...)` пишутся в самом тестовом файле. Клиент «Мария», флорист «Иванова».

Run → FAIL.

- [ ] **Step 2:** SQL-константы и три функции в `ui/orders.py`.
- [ ] **Step 3:** Run `pytest tests -v` → PASS.
- [ ] **Step 4: Commit** — «Логика оформления заказа одной транзакцией».

---

### Задача 6: Экраны заказов

**Files:**
- Modify: `app/sql.py`, `app/ui/orders.py`, `app/main.py`
- Test: `tests/test_orders.py` (добавить), `tests/test_ui_smoke.py`

**Interfaces:**
- Consumes: `validate_order`, `save_order`, `price_preview` из задачи 5; `RecordDialog` и конфиг «Клиенты» из `DIRECTORIES` (задача 3); `TEMPLATES_BY_FLORIST`, `TEMPLATE_ITEMS` (задача 4).
- Produces (`sql.py`):
  - `ORDERS_LIST` — колонки: id, №, дата, клиент, флорист, курьер (`COALESCE(…, 'самовывоз')`), оплата, сумма. Сумма = Σ `цена_продажи` букетов + Σ `количество × цена` отдельных растений, через подзапросы;
  - `ORDER_HEADER` (id);
  - `ORDER_BOUQUETS` (заказ_id) — колонки: id, шаблон (`COALESCE(ш.название, 'индивидуальный')`), сложность, время, цена продажи, `рекоменд_цена(б.id)`;
  - `BOUQUET_ITEMS` (букет_id) — колонки: растение, количество, закупочная цена;
  - `ORDER_PLANTS` (заказ_id) — колонки: растение, количество, цена, сумма.
- Produces (`ui/orders.py`):
  - `OrdersTab(QWidget)` — `refresh()`, кнопки «Оформить», «Просмотр», «Удалить», «Обновить»;
  - `OrderViewDialog(QDialog)` — `__init__(parent, order_id)`;
  - `OrderDialog(QDialog)` — `__init__(parent)`; метод `order() -> dict` собирает `Order` из виджетов;
  - `BouquetDialog(QDialog)` — `__init__(parent, florist_id, bouquet: dict | None)`; метод `bouquet() -> dict`.

Поведение — спецификация 6.5:
- клиент выбирается через `QComboBox` с `QCompleter` в режиме `MatchContains`, так что поиск работает и по телефону;
- кнопка «Новый клиент…» открывает `RecordDialog` с конфигом «Клиенты», вызывает `db.execute(insert)` и выбирает новый id;
- поля доставки неактивны, пока выбран самовывоз;
- при выборе шаблона его состав копируется в `BouquetDialog`;
- рекомендуемая цена пересчитывается через `price_preview` при каждом изменении состава;
- `цена_продажи` следует за рекомендуемой, пока пользователь не изменил её вручную;
- «Сохранить» сначала вызывает `validate_order`; если есть текст ошибки, показывается `QMessageBox`. Затем вызывается `save_order`; при `psycopg2.Error` показывается `show_error`, диалог остаётся открытым;
- удаление заказа подтверждается текстом «Заказ будет отменён, растения вернутся на склад. Удалить?».

- [ ] **Step 1: Тесты, падающие**
  - `test_orders_list_sum`: для заказа из `save_order` (один букет с ценой 1500.00 + 2 × цена растения) сумма в `ORDERS_LIST` равна `1500.00 + 2 × цена`.
  - `test_order_bouquets_has_recommended_price`: колонка `рекоменд_цена` в `ORDER_BOUQUETS` равна `RECOMMENDED_PRICE`.
  - `test_order_dialog_builds_order(qapp)`: программно заполнить `OrderDialog` (клиент «Мария», флорист «Иванова», самовывоз, один букет через `BouquetDialog`, созданный из шаблона «Классика»). Проверить: `validate_order(dlg.order()) is None`; у букета `шаблон_id` равен id «Классики»; состав `[(rose, 7), (eucalyptus, 3)]`; `цена_продажи == Decimal("1600.00")`.
  - `test_ui_smoke`: вкладка «Заказы» обновляется.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** SQL-константы и четыре класса.
- [ ] **Step 4:** Run `pytest tests -v` → PASS.
- [ ] **Step 5: Ручная проверка** — сценарии 6–10 спецификации через окно:
  - найти клиента по телефону `+79160000001`;
  - создать нового клиента из заказа;
  - оформить заказ с букетом по шаблону с изменённым составом, индивидуальным букетом и отдельным растением; во вкладке «Растения» остатки уменьшились;
  - просмотреть заказ;
  - удалить заказ — остатки вернулись;
  - попытаться продать больше остатка — сообщение триггера, заказ не появился.
- [ ] **Step 6: Commit** — «Экраны заказов».

---

### Задача 7: Заявки на закупку

**Files:**
- Modify: `app/sql.py`, `app/main.py`
- Create: `app/ui/purchases.py`
- Test: `tests/test_purchases.py`

**Interfaces:**
- Produces (`sql.py`):
  - `PURCHASES_LIST` (`%s::text` статус или NULL — все, передаётся дважды) — колонки: id, №, дата, растение, поставщик, срок, количество, ожидаемая дата, статус;
  - `PURCHASES_GENERATE` = `CALL сформировать_заявки()`;
  - `PURCHASES_COUNT` = количество заявок;
  - `PURCHASE_SET_STATUS` (статус, id).
- Produces (`ui/purchases.py`):
  - `PurchasesTab(QWidget)` — `refresh()`, фильтр по статусу («новая», «выполнена», «отменена», «все»), кнопки «Сформировать заявки», «Товар получен», «Отменить заявку», «Обновить»;
  - после формирования показывается «Добавлено заявок: N» (разница `PURCHASES_COUNT` до и после);
  - кнопки статуса неактивны, если у выбранной заявки статус не «новая».

- [ ] **Step 1: Тесты, падающие**
  - `test_generate_creates_request`: поднять `мин_остаток` одного растения выше остатка (UPDATE в тесте), вызвать `PURCHASES_GENERATE` — количество новых заявок по этому растению стало ≥ 1. Повторный вызов дублей не создаёт.
  - `test_receive_increases_stock`: для новой заявки `PURCHASE_SET_STATUS ('выполнена', id)` — остаток вырос ровно на количество из заявки.
  - `test_closed_request_is_frozen`: повторный `PURCHASE_SET_STATUS` по закрытой заявке даёт `psycopg2.Error`, `error_text` содержит «уже закрыта».
  - `test_filter_by_status`: `PURCHASES_LIST` с 'выполнена' возвращает только выполненные, с `None` — все.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** SQL-константы и `PurchasesTab`.
- [ ] **Step 4:** Run `pytest tests -v` → PASS.
- [ ] **Step 5: Ручная проверка** — сценарий 12.
- [ ] **Step 6: Commit** — «Заявки на закупку».

---

### Задача 8: Отчёты и XML

**Files:**
- Modify: `app/sql.py`, `app/main.py`
- Create: `app/ui/reports.py`
- Test: `tests/test_reports.py`

**Interfaces:**
- Produces (`sql.py`): `REPORT_1` … `REPORT_7`. Тексты — листинги 3.7–3.13 с изменениями из спецификации 6.2:
  - `REPORT_2` — параметры `(с, с, по, по)`, каждый `%s::date`, может быть `None`;
  - `REPORT_3` — параметры `(с, по)`, условие `з.дата >= %s AND з.дата < %s::date + 1`.
- Produces (`ui/reports.py`):
  - `REPORTS: list[tuple[str, str, str]]` — `(название, sql, вид_параметров)`, где `вид_параметров` ∈ {`none`, `optional_period`, `period`};
  - `ReportsTab(QWidget)` — `refresh()` ничего не делает;
  - для отчёта 6 результат показывается в `QPlainTextEdit` с форматированием `xml.dom.minidom.parseString(...).toprettyxml(indent="  ")`; кнопка «Сохранить XML…» (`QFileDialog.getSaveFileName`, фильтр `*.xml`) записывает файл в `utf-8`.

- [ ] **Step 1: Тесты, падающие** (сценарий 13)
  ```python
  @pytest.mark.parametrize("n", [1, 4, 5, 6, 7])
  def test_report_equals_listing(n):
      assert db.fetch(getattr(sql, f"REPORT_{n}"))[1] == run_block(n)

  def test_report_2_without_period_equals_listing():
      assert db.fetch(sql.REPORT_2, (None, None, None, None))[1] == run_block(2)

  def test_report_2_period_filters():
      rows = db.fetch(sql.REPORT_2, (d1, d1, d2, d2))[1]
      assert rows and all(d1 <= r[1] <= d2 for r in rows)

  def test_report_3_equals_listing_dates():   # в листинге 3.9 '2026-01-01' … < '2026-10-01'
      assert db.fetch(sql.REPORT_3, (date(2026, 1, 1), date(2026, 9, 30)))[1] == run_block(3)

  def test_reports_registry():
      assert [p for _, _, p in REPORTS] == ["none", "optional_period", "period", "none", "none", "none", "none"]

  def test_xml_pretty_and_grouped():
      xml_text = db.fetch_value(sql.REPORT_6)
      doc = minidom.parseString(xml_text)
      assert doc.documentElement.tagName == "прайс_лист" and doc.getElementsByTagName("категория")
  ```
  `run_block(n)` выполняет блок `-- Запрос N` из `database/запросы.sql` (`query_blocks()` из `conftest.py`).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Константы `REPORT_*` и `ReportsTab`. Значения дат по умолчанию: 1 января текущего года — сегодня.
- [ ] **Step 4:** Run `pytest tests -v` → PASS.
- [ ] **Step 5: Ручная проверка** — выполнить все 7 отчётов в окне, сохранить XML и открыть файл (сценарий 14).
- [ ] **Step 6: Commit** — «Отчёты и экспорт XML».

---

### Задача 9: Финальная проверка, README, скриншоты

**Files:**
- Modify: `README.md` (уточнить инструкцию по факту, снять пометку «Статус: идёт разработка»)
- Create: `docs/проверка/отчёт_о_проверке.md`, `docs/проверка/скриншоты/*.png`

- [ ] **Step 1: Чистый запуск по README.** На пустом контейнере выполнить шаги README по порядку, команды копировать из файла. Если какой-то шаг не сработал, исправить README.
  Expected: `python app/main.py` открывает окно с данными.
- [ ] **Step 2:** Run `.venv\Scripts\python -m pytest tests -v` → все тесты PASS. Вывод сохранить в отчёт.
- [ ] **Step 3: Ручной прогон** сценариев 1–14 спецификации в окне. Для каждого записать в `отчёт_о_проверке.md`: что сделано, ожидание, фактический результат.
- [ ] **Step 4: Скриншоты** — 10 экранов из раздела 11 спецификации, файлы `01_растения.png` … `10_xml.png`.
- [ ] **Step 5:** Проверка на запрещённое. Run:
  - `git grep -n -E "f\"|f'|\.format\(" -- app/sql.py`
  - `git grep -n -i -E "select .+ from|insert into|delete from|update [а-я_]+ set" -- app ":!app/sql.py"`

  Expected: в `sql.py` нет форматирования строк, вне `sql.py` нет SQL. f-строки в текстах сообщений интерфейса разрешены.
- [ ] **Step 6: Commit** — «README, отчёт о проверке, скриншоты».
