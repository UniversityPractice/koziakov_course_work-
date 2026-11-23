"""Схема БД и тестовые данные: всё на месте, отчёты не пустые."""
from decimal import Decimal

import pytest

from conftest import query_blocks


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
