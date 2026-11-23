"""Модуль db: чтение, запись, транзакции, тексты ошибок."""
from decimal import Decimal

import psycopg2
import pytest

import db


def test_fetch_returns_columns_and_rows():
    cols, rows = db.fetch("select название, коэф_наценки from категории where название = %s", ("Розы",))
    assert cols == ["название", "коэф_наценки"]
    assert rows == [("Розы", Decimal("2.00"))]


def test_execute_returning_id_uses_sequence():
    new_id = db.execute("insert into категории (название, коэф_наценки) values (%s, %s) returning id",
                        ("Тест-кат", 1.2))
    assert isinstance(new_id, int)
    assert db.fetch_value("select currval('посл_категории')") == new_id
    db.execute("delete from категории where id = %s", (new_id,))


def test_transaction_rolls_back_everything():
    before = db.fetch_value("select count(*) from категории")
    with pytest.raises(psycopg2.Error):
        with db.transaction() as cur:
            cur.execute("insert into категории (название, коэф_наценки) values ('X1', 1.5)")
            cur.execute("insert into категории (название, коэф_наценки) values ('X2', 0.5)")
    assert db.fetch_value("select count(*) from категории") == before


def test_connection_usable_after_error():
    with pytest.raises(psycopg2.Error):
        db.execute("insert into категории (название, коэф_наценки) values ('Розы', 2)")
    assert db.fetch_value("select 1") == 1
    new_id = db.execute("insert into категории (название, коэф_наценки) values ('X3', 1.1) returning id")
    db.execute("delete from категории where id = %s", (new_id,))


@pytest.mark.parametrize("sql_text, fragment", [
    ("delete from категории where название = 'Розы'", "используется в таблице «растения»"),
    ("insert into категории (название, коэф_наценки) values ('Розы', 2)", "уже есть: название = Розы"),
    ("insert into категории (название, коэф_наценки) values ('Y', 0.5)", "Недопустимое значение"),
    ("insert into категории (название, коэф_наценки) values (null, 2)", "Не заполнено поле «название»"),
])
def test_error_text_by_code(sql_text, fragment):
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql_text)
    assert fragment in db.error_text(exc.value)


def test_error_text_trigger_message():
    with pytest.raises(psycopg2.Error) as exc:
        db.execute("insert into списания (растение_id, количество, причина) "
                   "select id, остаток + 1, 'брак' from растения where название = 'Роза красная'")
    assert db.error_text(exc.value).startswith("Недостаточно «Роза красная» на складе")


def test_error_text_without_pgcode():
    with pytest.raises(psycopg2.OperationalError) as exc:
        psycopg2.connect(host="localhost", port=1, dbname="x", user="x", password="x", connect_timeout=2)
    assert db.error_text(exc.value)


def test_config_has_connection_keys():
    assert set(db.read_config()) == {"host", "port", "dbname", "user", "password"}
