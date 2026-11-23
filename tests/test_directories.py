"""Справочники: ввод, редактирование, удаление, понятные ошибки."""
from decimal import Decimal

import psycopg2
import pytest

import db
import sql
from ui.directories import DIRECTORIES, RecordDialog, directory


def lookup_id(lookup_sql, label_start):
    return next(i for i, label in db.fetch(lookup_sql)[1] if label.startswith(label_start))


def stock(name):
    return db.fetch_value("select остаток from растения where название = %s", (name,))


def normalize(row):
    return tuple(float(v) if isinstance(v, Decimal) else v for v in row)


def samples(title):
    rose_cat = lookup_id(sql.CATEGORIES_LOOKUP, "Розы")
    supplier = lookup_id(sql.SUPPLIERS_LOOKUP, "Зелёный дом")
    eucalyptus = lookup_id(sql.PLANTS_LOOKUP, "Эвкалипт")
    return {
        "Категории": (("Тест-кат", 1.30), ("Тест-кат-2", 1.40)),
        "Поставщики": (("Тест-пост", "+70000000000", 2), ("Тест-пост-2", None, 3)),
        "Растения": (("Тест-растение", "горшечный", rose_cat, supplier, 100.00, 10, 2),
                     ("Тест-растение", "горшечный", rose_cat, supplier, 110.00, 20, 2)),
        "Сотрудники": (("Тестов Т.Т.", "курьер", None), ("Тестов Т.Т.", "флорист", "+70000000001")),
        "Клиенты": (("Тест-клиент", None, None), ("Тест-клиент", "+70000000002", "t@t.ru")),
        "Списания": ((eucalyptus, 2, "брак"), (eucalyptus, 3, "увядание")),
    }[title]


@pytest.mark.parametrize("cfg", DIRECTORIES, ids=lambda c: c["title"])
def test_crud_roundtrip(cfg):
    ins, upd = samples(cfg["title"])
    new_id = db.execute(cfg["insert"], ins)
    assert normalize(db.fetch(cfg["get"], (new_id,))[1][0]) == ins
    db.execute(cfg["update"], upd + (new_id,))
    assert normalize(db.fetch(cfg["get"], (new_id,))[1][0]) == upd
    assert any(r[0] == new_id for r in db.fetch(cfg["list"])[1])
    db.execute(cfg["delete"], (new_id,))
    assert db.fetch(cfg["get"], (new_id,))[1] == []


def test_writeoff_moves_stock():
    eucalyptus = lookup_id(sql.PLANTS_LOOKUP, "Эвкалипт")
    before = stock("Эвкалипт")
    wid = db.execute(sql.WRITEOFF_INSERT, (eucalyptus, 2, "брак"))
    assert stock("Эвкалипт") == before - 2
    db.execute(sql.WRITEOFF_UPDATE, (eucalyptus, 3, "брак", wid))
    assert stock("Эвкалипт") == before - 3
    db.execute(sql.WRITEOFF_DELETE, (wid,))
    assert stock("Эвкалипт") == before


def test_writeoff_over_stock_rejected():
    eucalyptus = lookup_id(sql.PLANTS_LOOKUP, "Эвкалипт")
    before = stock("Эвкалипт")
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql.WRITEOFF_INSERT, (eucalyptus, before + 1, "брак"))
    assert db.error_text(exc.value).startswith("Недостаточно «Эвкалипт» на складе")
    assert stock("Эвкалипт") == before


def test_two_clients_without_phone():
    a = db.execute(sql.CLIENT_INSERT, ("Без телефона 1", None, None))
    b = db.execute(sql.CLIENT_INSERT, ("Без телефона 2", None, None))
    assert a != b
    db.execute(sql.CLIENT_DELETE, (a,))
    db.execute(sql.CLIENT_DELETE, (b,))


@pytest.mark.parametrize("delete_sql, lookup_sql, label", [
    (sql.CATEGORY_DELETE, sql.CATEGORIES_LOOKUP, "Розы"),
    (sql.SUPPLIER_DELETE, sql.SUPPLIERS_LOOKUP, "Эквадор Роуз"),
    (sql.PLANT_DELETE, sql.PLANTS_LOOKUP, "Роза красная"),
    (sql.EMPLOYEE_DELETE, sql.FLORISTS_LOOKUP, "Иванова"),
    (sql.CLIENT_DELETE, sql.CLIENTS_LOOKUP, "Мария"),
])
def test_delete_used_record_gives_clear_error(delete_sql, lookup_sql, label):
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(delete_sql, (lookup_id(lookup_sql, label),))
    assert "используется" in db.error_text(exc.value)


def test_duplicate_and_check_errors():
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql.CLIENT_INSERT, ("Двойник", "+79160000001", None))
    assert "уже есть" in db.error_text(exc.value)
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql.CATEGORY_INSERT, ("Дешёвые", 0.5))
    assert "Недопустимое значение" in db.error_text(exc.value)


def test_plants_list_flags_low_stock():
    rows = db.fetch(sql.PLANT_LIST)[1]
    assert sum(1 for r in rows if r[directory("Растения")["highlight_col"]]) >= 3


def test_lookups_filter_roles():
    florists = [label for _, label in db.fetch(sql.FLORISTS_LOOKUP)[1]]
    couriers = [label for _, label in db.fetch(sql.COURIERS_LOOKUP)[1]]
    assert "Петров Игорь Олегович" not in florists and "Иванова Анна Сергеевна" in florists
    assert "Иванова Анна Сергеевна" not in couriers and "Петров Игорь Олегович" in couriers


def test_record_dialog_empty_text_is_none(qapp):
    dlg = RecordDialog(None, directory("Клиенты"))
    dlg.widgets[0].setText("  Ольга ")
    assert dlg.values() == ("Ольга", None, None)


def test_record_dialog_edit_fills_and_saves(qapp):
    cfg = directory("Растения")
    plant_id = lookup_id(sql.PLANTS_LOOKUP, "Роза красная")
    values = db.fetch(cfg["get"], (plant_id,))[1][0]
    dlg = RecordDialog(None, cfg, values, plant_id)
    assert normalize(dlg.values()) == normalize(values)
    dlg.widgets[6].setValue(55)          # мин. остаток
    dlg.save()
    assert db.fetch_value("select мин_остаток from растения where id = %s", (plant_id,)) == 55
    db.execute(cfg["update"], values + (plant_id,))
