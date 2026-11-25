"""Расчёт розничной стоимости букета: функция рекоменд_цена по составу и страница /price."""
from decimal import Decimal

import pytest

import db
import sql
from conftest import read_script


def one(query, params=None):
    return db.fetch_value(query, params)


def plant(name):
    return one("select id from растения where название = %s", (name,))


def text(response):
    return response.get_data(as_text=True)


def classic_id():
    return one("select id from шаблоны where название = 'Классика'")


# --- функция базы -------------------------------------------------------------

def test_function_example_from_note():
    # пример из записки: 7 × 95 × 2,00 + 3 × 60 × 1,50 = 1600
    price = one(sql.RECOMMENDED_PRICE_BY_ITEMS, ([plant("Роза красная"), plant("Эвкалипт")], [7, 3]))
    assert price == Decimal("1600.00")


def test_function_empty_composition_is_zero():
    assert one(sql.RECOMMENDED_PRICE_BY_ITEMS, ([], [])) == 0
    assert one("select рекоменд_цена(null::int[], null::int[])") == 0


def test_both_functions_agree_on_every_bouquet():
    """рекоменд_цена(букет_id) и рекоменд_цена(растения[], количества[]) считают одинаково."""
    assert one("""select count(*) from букеты б
                  where рекоменд_цена(б.id) <> (select рекоменд_цена(array_agg(растение_id), array_agg(количество))
                                                from состав_букета where букет_id = б.id)""") == 0
    assert one("select count(*) from букеты") > 50


def test_update_script_is_repeatable(cur):
    cur.execute(read_script("обновление_расчёт_цены.sql"))
    cur.execute(read_script("обновление_расчёт_цены.sql"))
    cur.execute("select рекоменд_цена(array[%s], array[2])", (plant("Эвкалипт"),))
    assert cur.fetchone()[0] == Decimal("180.00")          # 2 × 60 × 1,5


def test_template_price_uses_function():
    florist = one("select флорист_id from шаблоны where id = %s", (classic_id(),))
    row = next(r for r in db.fetch(sql.TEMPLATE_LIST, (florist,))[1] if r[0] == classic_id())
    assert row[4] == Decimal("1600.00")
    assert db.fetch(sql.TEMPLATE_GET, (classic_id(),))[1][0][4] == Decimal("1600.00")


# --- страница -----------------------------------------------------------------

def test_price_page_empty(client):
    page = text(client.get("/price"))
    assert "Расчёт розничной стоимости букета" in page and "Добавьте растения" in page
    assert "0 ₽" in page or "0.00 ₽" in page or ">0<" in page


def test_price_page_from_template(client):
    page = text(client.get("/price", query_string={"template": classic_id()}))
    assert "Роза красная" in page and "Эвкалипт" in page
    assert "1330.00" in page and "270.00" in page and "<b>1600.00 ₽</b>" in page


def test_price_page_manual_composition(client):
    page = text(client.post("/price", data={
        "p_plant": [str(plant("Эвкалипт")), str(plant("Эвкалипт")), ""], "p_qty": ["1", "1", ""],
        "action": "recalc"}))
    assert "<b>180.00 ₽</b>" in page                     # одинаковые строки сложены: 2 × 60 × 1,5


def test_price_page_from_bouquet(client):
    bouquet_id, order_id, expected = db.fetch(
        "select id, заказ_id, рекоменд_цена(id) from букеты order by id limit 1")[1][0]
    page = text(client.post("/price", data={"bouquet": bouquet_id, "action": "bouquet"}))
    assert f"рекоменд_цена({bouquet_id})" in page and f"заказа №{order_id}" in page
    assert f"<b>{expected} ₽</b>" in page                # итог по составу = функции по id
    assert client.get("/price", query_string={"bouquet": bouquet_id}).status_code == 200


@pytest.mark.parametrize("data, message", [
    ({"bouquet": "999999", "action": "bouquet"}, "Букета с номером «999999» нет"),
    ({"template": "", "action": "template"}, "Выберите шаблон"),
])
def test_price_page_errors(client, data, message):
    assert message in text(client.post("/price", data=data))


def test_price_page_clear(client):
    page = text(client.post("/price", data={"p_plant": str(plant("Эвкалипт")), "p_qty": "3", "action": "clear"}))
    assert "Добавьте растения" in page


def test_links_to_price_page(client):
    assert f"/price?template={classic_id()}" in text(client.get(f"/recipes/{classic_id()}"))
    order_id = one("select min(заказ_id) from букеты")
    assert "/price?bouquet=" in text(client.get(f"/orders/{order_id}"))
