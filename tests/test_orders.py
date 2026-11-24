"""Статус заказа: склад списывается при оформлении, вручённый заказ не меняется."""
import psycopg2
import pytest

import db
import sql


def stock(name="Эвкалипт"):
    return db.fetch_value("select остаток from растения where название = %s", (name,))


def status(order_id):
    return db.fetch("select статус, время_вручения from заказы where id = %s", (order_id,))[1][0]


def new_order(courier=True, qty=2):
    """Заказ с одним отдельным растением (Эвкалипт); тр_склад списывает его сразу."""
    with db.transaction() as cur:
        cur.execute("""
            insert into заказы (клиент_id, флорист_id, способ_оплаты, курьер_id, адрес_доставки, время_доставки)
            select (select min(id) from клиенты),
                   (select min(id) from сотрудники where должность = 'флорист'),
                   'карта',
                   case when %s then (select min(id) from сотрудники where должность = 'курьер') end,
                   case when %s then 'Москва, тестовая ул., 1' end,
                   case when %s then now() + interval '2 hours' end
            returning id""", (courier, courier, courier))
        order_id = cur.fetchone()[0]
        cur.execute("""insert into растения_в_заказе (заказ_id, растение_id, количество)
                       select %s, id, %s from растения where название = 'Эвкалипт'""", (order_id, qty))
    return order_id


def set_status(order_id, value):
    db.execute(sql.ORDER_SET_STATUS, (value, order_id))


def test_seed_statuses():
    # только заказы из тестовых данных (все они не позже вчерашнего дня)
    rows = db.fetch("select статус, count(*), count(время_вручения) from заказы "
                    "where дата < current_date group by статус")[1]
    counts = {s: (n, with_time) for s, n, with_time in rows}
    assert counts["принят"] == (1, 0) and counts["в доставке"] == (1, 0)
    assert counts["вручён"][0] == counts["вручён"][1] > 50


def test_new_order_is_accepted_and_stock_taken():
    before = stock()
    order_id = new_order()
    assert status(order_id) == ("принят", None)
    assert stock() == before - 2


def test_cancel_accepted_order_returns_stock():
    before = stock()
    db.execute(sql.ORDER_DELETE, (new_order(),))
    assert stock() == before


def test_delivery_lifecycle():
    before = stock()
    order_id = new_order()
    set_status(order_id, "в доставке")
    set_status(order_id, "не вручён")
    set_status(order_id, "в доставке")        # повторная доставка
    set_status(order_id, "вручён")
    value, delivered_at = status(order_id)
    assert value == "вручён" and delivered_at is not None
    assert stock() == before - 2               # склад списан один раз, при оформлении


@pytest.mark.parametrize("steps, bad, message", [
    (["вручён"], "не вручён", "уже вручён"),
    (["в доставке"], "принят", "в статус «принят» нельзя"),
])
def test_forbidden_transitions(steps, bad, message):
    order_id = new_order()
    for s in steps:
        set_status(order_id, s)
    with pytest.raises(psycopg2.Error) as exc:
        set_status(order_id, bad)
    assert message in db.error_text(exc.value)


def test_pickup_cannot_go_to_courier():
    order_id = new_order(courier=False)
    with pytest.raises(psycopg2.Error) as exc:
        set_status(order_id, "в доставке")
    assert "самовывоз" in db.error_text(exc.value)
    set_status(order_id, "вручён")             # самовывоз: сразу вручён
    assert status(order_id)[0] == "вручён"


@pytest.mark.parametrize("value", ["в доставке", "вручён", "не вручён"])
def test_cannot_cancel_after_handover(value):
    order_id = new_order()
    if value == "не вручён":
        set_status(order_id, "в доставке")
    set_status(order_id, value)
    before = stock()
    with pytest.raises(psycopg2.Error) as exc:
        db.execute(sql.ORDER_DELETE, (order_id,))
    assert "отменить его нельзя" in db.error_text(exc.value)
    assert stock() == before


# --- Страница заказов --------------------------------------------------

def text(response):
    return response.get_data(as_text=True)


@pytest.mark.parametrize("f", ["активные", "принят", "в доставке", "вручён", "не вручён", "все", "мусор"])
def test_orders_page_filters(client, f):
    assert client.get("/orders", query_string={"status": f}).status_code == 200


def test_orders_page_flow(client):
    order_id = new_order()
    page = text(client.get("/orders"))
    assert f'href="/orders/{order_id}">{order_id}</a>' in page and "Передать курьеру" in page

    page = text(client.post(f"/orders/{order_id}/delivery", follow_redirects=True))
    assert "Заказ передан курьеру" in page
    page = text(client.post(f"/orders/{order_id}/delivered", follow_redirects=True))
    assert "Заказ вручён" in page
    assert status(order_id)[0] == "вручён"

    page = text(client.post(f"/orders/{order_id}/cancel", follow_redirects=True))
    assert "отменить его нельзя" in page


def test_orders_page_cancel(client):
    before = stock()
    order_id = new_order()
    page = text(client.post(f"/orders/{order_id}/cancel", follow_redirects=True))
    assert "растения вернулись на склад" in page
    assert stock() == before


def test_orders_unknown_action_404(client):
    assert client.post("/orders/1/explode").status_code == 404


# --- Состав в списке и фильтр по курьеру ------------------------------------

def list_rows(filter_="все", courier=None):
    columns, rows = db.fetch(sql.ORDER_LIST, {"фильтр": filter_, "курьер": courier})
    return [dict(zip(columns, r)) | {"id": r[0]} for r in rows]


def test_list_shows_composition():
    order_id = new_order(qty=2)
    row = next(r for r in list_rows() if r["id"] == order_id)
    assert row["Состав"] == "Эвкалипт × 2"
    # заказ с букетом по шаблону и индивидуальным букетом
    composed = [r["Состав"] for r in list_rows()]
    assert any("букет «" in c for c in composed) and any("индивидуальный букет" in c for c in composed)
    assert all(c for c in composed)          # у каждого заказа есть состав


def test_courier_filter():
    courier = db.fetch_value("select min(id) from сотрудники where должность = 'курьер'")
    mine = list_rows(courier=courier)
    assert mine and all(r["Курьер"] == db.fetch_value("select фио from сотрудники where id = %s", (courier,))
                        for r in mine)
    pickup = list_rows(courier=0)
    assert pickup and all(r["Адрес"] == "самовывоз" for r in pickup)
    assert len(mine) + len(pickup) <= len(list_rows())


def test_orders_page_courier_filter(client):
    courier = db.fetch_value("select min(id) from сотрудники where должность = 'курьер'")
    page = text(client.get("/orders", query_string={"status": "все", "courier": courier}))
    assert "Заказов у курьера в выбранном статусе" in page and "№ заказа" in page and "Состав" in page
    assert f'status=%D0%B2%D1%81%D0%B5&amp;courier={courier}' in page or f"courier={courier}" in page
    assert client.get("/orders", query_string={"courier": "abc"}).status_code == 200


def test_action_keeps_filters_or_returns_to_view(client):
    order_id = new_order()
    response = client.post(f"/orders/{order_id}/delivery", query_string={"status": "все", "courier": "7"})
    assert "courier=7" in response.headers["Location"] and "/orders?" in response.headers["Location"]
    response = client.post(f"/orders/{order_id}/delivered", query_string={"back": "view"})
    assert response.headers["Location"].endswith(f"/orders/{order_id}")
