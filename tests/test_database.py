"""Схема БД и тестовые данные: всё на месте, отчёты не пустые."""
from decimal import Decimal

import psycopg2
import pytest

from conftest import TEST_PARAMS, query_blocks, read_script


def run_block(cur, n):
    cur.execute(query_blocks()[n])
    return cur.fetchall()


def test_13_tables(cur):
    cur.execute("select count(*) from information_schema.tables where table_schema = 'public'")
    assert cur.fetchone()[0] == 13


def test_10_sequences(cur):
    cur.execute("select count(*) from information_schema.sequences where sequence_name like 'посл_%'")
    assert cur.fetchone()[0] == 10


def test_recommended_price_example(cur):
    # пример из раздела 3.2: 7 × 95 × 2,00 + 3 × 60 × 1,50 = 1600
    cur.execute("""select sum(сш.количество * р.закупочная_цена * к.коэф_наценки)
                   from состав_шаблона сш join шаблоны ш on ш.id = сш.шаблон_id
                   join растения р on р.id = сш.растение_id
                   join категории к on к.id = р.категория_id
                   where ш.название = 'Классика'""")
    assert cur.fetchone()[0] == Decimal("1600.00")


@pytest.mark.parametrize("n", range(1, 8))
def test_every_report_has_rows(cur, n):
    rows = run_block(cur, n)
    assert rows
    if n == 6:
        assert "<категория>" in rows[0][0]


def test_q5_has_12_months_with_a_zero(cur):
    rows = run_block(cur, 5)
    assert len(rows) == 12 and any(r[1] == 0 for r in rows)


def test_q4_at_least_3_low_stock(cur):
    assert len(run_block(cur, 4)) >= 3


def test_auto_purchase_requests_exist(cur):
    cur.execute("select count(*) from заявки_на_закупку where статус = 'новая'")
    assert cur.fetchone()[0] >= 1


def test_all_bouquet_kinds(cur):
    cur.execute("select count(distinct сложность), "
                "count(*) filter (where шаблон_id is null), "
                "count(*) filter (where шаблон_id is not null) from букеты")
    kinds, individual, by_template = cur.fetchone()
    assert kinds == 3 and individual > 0 and by_template > 0


def test_fixture_entities(cur):
    cur.execute("select остаток from растения where название in ('Роза красная', 'Эвкалипт')")
    assert [r[0] >= 100 for r in cur.fetchall()] == [True, True]
    cur.execute("select count(*) from клиенты where имя = 'Мария' and телефон = '+79160000001'")
    assert cur.fetchone()[0] == 1
    cur.execute("select count(*) from букеты б join шаблоны ш on ш.id = б.шаблон_id "
                "where ш.название = 'Весенний'")
    assert cur.fetchone()[0] >= 1


TABLES = ["категории", "поставщики", "растения", "сотрудники", "шаблоны", "состав_шаблона",
          "клиенты", "заказы", "растения_в_заказе", "букеты", "состав_букета", "списания",
          "заявки_на_закупку"]


@pytest.fixture(scope="module")
def full_cur():
    """Отдельная база: схема + тестовые + дополнительные данные + текущие заказы (как в docker compose)."""
    params = {**TEST_PARAMS, "dbname": "florist_full_test"}
    admin = psycopg2.connect(**{**TEST_PARAMS, "dbname": "postgres"})
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute("DROP DATABASE IF EXISTS florist_full_test WITH (FORCE)")
        c.execute("CREATE DATABASE florist_full_test ENCODING 'UTF8' TEMPLATE template0")
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    with conn.cursor() as c:
        for name in ("флористический_центр.sql", "тестовые_данные.sql", "дополнительные_данные.sql",
                     "текущие_заказы.sql"):
            c.execute(read_script(name))
        yield c
    conn.close()
    with admin.cursor() as c:
        c.execute("DROP DATABASE florist_full_test WITH (FORCE)")
    admin.close()


def test_more_data_volume(full_cur):
    counts = {}
    for t in TABLES:
        full_cur.execute(f"select count(*) from {t}")
        counts[t] = full_cur.fetchone()[0]
    assert counts["категории"] >= 20 and counts["поставщики"] >= 25
    assert all(n >= 100 for t, n in counts.items() if t not in ("категории", "поставщики")), counts


def test_more_data_consistent(full_cur):
    # у каждого заказа есть букет или отдельное растение, у букета — состав и цена
    full_cur.execute("""select count(*) from заказы з
                        where not exists (select 1 from букеты where заказ_id = з.id)
                          and not exists (select 1 from растения_в_заказе where заказ_id = з.id)""")
    assert full_cur.fetchone()[0] == 0
    full_cur.execute("""select count(*) from букеты б
                        where б.цена_продажи <= 0
                           or not exists (select 1 from состав_букета where букет_id = б.id)""")
    assert full_cur.fetchone()[0] == 0
    full_cur.execute("select count(*) from заказы where дата >= now()")
    assert full_cur.fetchone()[0] == 0


@pytest.mark.parametrize("n", range(1, 8))
def test_more_data_reports(full_cur, n):
    assert run_block(full_cur, n)


def test_current_orders_in_work(full_cur):
    # в работе есть заказы во всех активных статусах, у доставок — курьер и адрес
    full_cur.execute("""select статус, count(*) from заказы where статус <> 'вручён' group by статус""")
    counts = dict(full_cur.fetchall())
    assert counts["принят"] >= 6 and counts["в доставке"] >= 5 and counts["не вручён"] >= 3
    full_cur.execute("""select count(*) from заказы where статус in ('в доставке', 'не вручён')
                        and (курьер_id is null or адрес_доставки is null or время_доставки is null)""")
    assert full_cur.fetchone()[0] == 0
    # «в доставке» — к ближайшим часам, «не вручён» — время уже прошло
    full_cur.execute("""select count(*) filter (where статус = 'в доставке' and время_доставки > now()),
                               count(*) filter (where статус = 'не вручён' and время_доставки < now())
                        from заказы""")
    upcoming, missed = full_cur.fetchone()
    assert upcoming >= 5 and missed >= 3


def test_current_orders_with_base_data_only():
    """Скрипт текущих заказов работает и без дополнительных данных."""
    params = {**TEST_PARAMS, "dbname": "florist_current_test"}
    admin = psycopg2.connect(**{**TEST_PARAMS, "dbname": "postgres"})
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute("DROP DATABASE IF EXISTS florist_current_test WITH (FORCE)")
        c.execute("CREATE DATABASE florist_current_test ENCODING 'UTF8' TEMPLATE template0")
    conn = psycopg2.connect(**params)
    conn.autocommit = True
    try:
        with conn.cursor() as c:
            for name in ("флористический_центр.sql", "тестовые_данные.sql", "текущие_заказы.sql"):
                c.execute(read_script(name))
            c.execute("select count(*) from заказы where дата > now() - interval '2 days' "
                      "and статус in ('принят', 'в доставке', 'не вручён')")
            assert c.fetchone()[0] >= 14
    finally:
        conn.close()
        with admin.cursor() as c:
            c.execute("DROP DATABASE florist_current_test WITH (FORCE)")
        admin.close()
