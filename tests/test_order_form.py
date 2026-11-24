"""Оформление заказа: черновик, пересчёт цен, проверки, сохранение одной транзакцией."""
from decimal import Decimal

import pytest
from werkzeug.datastructures import MultiDict

import db
import orders
import sql


def one(query, params=None):
    return db.fetch_value(query, params)


def plant(name):
    return one("select id from растения where название = %s", (name,))


def stock(name):
    return one("select остаток from растения where название = %s", (name,))


def orders_count():
    return one("select count(*) from заказы")


@pytest.fixture
def ids():
    florist = one("select id from сотрудники where фио = 'Иванова Анна Сергеевна'")
    return {
        "client": one("select id from клиенты where телефон = '+79160000001'"),
        "florist": florist,
        "courier": one("select id from сотрудники where должность = 'курьер' order by id limit 1"),
        "template": one("select id from шаблоны where флорист_id = %s order by id limit 1", (florist,)),
        "other_template": one("select id from шаблоны where флорист_id <> %s order by id limit 1", (florist,)),
    }


def draft_with(ids, bouquets=(), plants=(), courier=False):
    draft = orders.empty_draft()
    draft.update(client=ids["client"], florist=ids["florist"])
    if courier:
        draft.update(courier=ids["courier"], address="Москва, ул. Цветочная, 1", time="2030-03-08T10:00")
    for items in bouquets:
        b = orders.empty_bouquet()
        b.update(items=list(items), minutes="20")
        draft["bouquets"].append(b)
    draft["plants"] = list(plants)
    return orders.recalc(draft)


# --- черновик из формы ----------------------------------------------------

def test_read_items_skips_empty_and_merges():
    assert orders.read_items(["5", "", "5", "7", "8"], ["2", "3", "1", "", "0"]) == [(5, 3)]


def test_read_draft_from_form():
    form = MultiDict([("client", "1"), ("florist", "2"), ("payment", "карта"), ("courier", ""),
                      ("b_count", "1"), ("b0_template", ""), ("b0_complexity", "средний"),
                      ("b0_minutes", "25"), ("b0_price", "1000"), ("b0_plant", "3"), ("b0_qty", "4"),
                      ("b0_plant", ""), ("b0_qty", ""), ("p_plant", "9"), ("p_qty", "1")])
    draft = orders.read_draft(form)
    assert draft["client"] == 1 and draft["courier"] is None and draft["payment"] == "карта"
    assert draft["bouquets"][0]["items"] == [(3, 4)] and draft["bouquets"][0]["complexity"] == "средний"
    assert draft["plants"] == [(9, 1)]


def test_actions_add_remove_template(ids):
    draft = draft_with(ids)
    orders.apply_action(draft, "add_bouquet")
    orders.apply_action(draft, "add_bouquet")
    draft["bouquets"][1]["template"] = ids["template"]
    orders.apply_action(draft, "template:1")
    assert draft["bouquets"][1]["items"] == orders.template_items(ids["template"]) != []
    orders.apply_action(draft, "remove:0")
    assert len(draft["bouquets"]) == 1 and draft["bouquets"][0]["template"] == ids["template"]
    orders.apply_action(draft, "remove:9")      # нет такого букета — ничего не происходит
    orders.apply_action(draft, "template:x")
    assert len(draft["bouquets"]) == 1


# --- пересчёт -----------------------------------------------------------

def test_recalc_template_fills_items_and_price(ids):
    draft = draft_with(ids)
    draft["bouquets"].append({**orders.empty_bouquet(), "template": ids["template"]})
    orders.recalc(draft)
    b = draft["bouquets"][0]
    assert b["items"] == orders.template_items(ids["template"])
    assert b["rec"] > 0 and b["price"] == str(b["rec"])
    assert draft["total"] == b["rec"]


def test_recalc_price_follows_rec_until_edited(ids):
    draft = draft_with(ids, bouquets=[[(plant("Эвкалипт"), 2)]])
    b = draft["bouquets"][0]
    first = b["rec"]
    b["items"] = [(plant("Эвкалипт"), 4)]
    orders.recalc(draft)
    assert b["rec"] == first * 2 and b["price"] == str(b["rec"])   # цену не трогали — следует за рекоменд.
    b["price"] = "999"
    b["items"] = [(plant("Эвкалипт"), 1)]
    orders.recalc(draft)
    assert b["price"] == "999"                                      # изменённую вручную не трогаем


def test_recalc_drops_other_florists_template(ids):
    draft = draft_with(ids)
    draft["bouquets"].append({**orders.empty_bouquet(), "template": ids["other_template"],
                              "items": [(plant("Эвкалипт"), 1)]})
    orders.recalc(draft)
    assert draft["bouquets"][0]["template"] is None
    assert draft["bouquets"][0]["items"] == [(plant("Эвкалипт"), 1)]


def test_total_includes_loose_plants(ids):
    draft = draft_with(ids, plants=[(plant("Эвкалипт"), 3)])
    retail = dict(db.fetch(sql.PLANT_RETAIL_PRICES, ([plant("Эвкалипт")],))[1])[plant("Эвкалипт")]
    assert draft["total"] == retail * 3


# --- проверки -------------------------------------------------------------

@pytest.mark.parametrize("change, message", [
    ({"client": None}, "клиента"),
    ({"florist": None}, "флориста"),
    ({"courier": 1, "address": ""}, "адрес"),
    ({"bouquets": [], "plants": []}, "букет или растение"),
])
def test_check_order_fields(ids, change, message):
    draft = draft_with(ids, bouquets=[[(plant("Эвкалипт"), 1)]])
    draft.update(change)
    assert message in orders.check(draft)


@pytest.mark.parametrize("change, message", [
    ({"items": []}, "нет ни одного растения"),
    ({"minutes": ""}, "время сборки"),
    ({"price": "abc"}, "цена"),
    ({"complexity": "лёгкий"}, "сложность"),
])
def test_check_bouquet_fields(ids, change, message):
    draft = draft_with(ids, bouquets=[[(plant("Эвкалипт"), 1)]])
    draft["bouquets"][0].update(change)
    assert message in orders.check(draft)


# --- сохранение -----------------------------------------------------------

def test_save_order_with_delivery(ids):
    rose, eucalyptus = plant("Роза красная"), plant("Эвкалипт")
    before = stock("Роза красная"), stock("Эвкалипт")
    draft = draft_with(ids, bouquets=[[(rose, 5), (eucalyptus, 2)]], plants=[(eucalyptus, 1)], courier=True)
    assert orders.check(draft) is None
    order_id = orders.save(draft)

    assert (stock("Роза красная"), stock("Эвкалипт")) == (before[0] - 5, before[1] - 3)
    header = db.fetch("select статус, курьер_id, адрес_доставки, время_доставки::text from заказы where id = %s",
                      (order_id,))[1][0]
    assert header == ("принят", ids["courier"], "Москва, ул. Цветочная, 1", "2030-03-08 10:00:00")
    bouquet_id, price = db.fetch("select id, цена_продажи from букеты where заказ_id = %s", (order_id,))[1][0]
    # черновик и функция рекоменд_цена считают одинаково, цену продажи взяли рекомендуемую
    assert one("select рекоменд_цена(%s)", (bouquet_id,)) == draft["bouquets"][0]["rec"] == price
    # цены позиций подставил триггер тр_склад
    assert one("select count(*) from состав_букета where букет_id = %s and закупочная_цена > 0",
               (bouquet_id,)) == 2
    assert one("select цена from растения_в_заказе where заказ_id = %s", (order_id,)) > 0


def test_save_pickup_ignores_delivery_fields(ids):
    draft = draft_with(ids, plants=[(plant("Эвкалипт"), 1)])
    draft.update(address="не нужен", recipient="кто-то")
    order_id = orders.save(draft)
    assert db.fetch("select курьер_id, адрес_доставки, получатель from заказы where id = %s",
                    (order_id,))[1][0] == (None, None, None)


def test_save_shortage_rolls_back_everything(ids):
    rose = plant("Роза красная")
    before_orders, before_rose, before_euc = orders_count(), stock("Роза красная"), stock("Эвкалипт")
    draft = draft_with(ids, bouquets=[[(plant("Эвкалипт"), 1)], [(rose, before_rose + 1)]])
    with pytest.raises(Exception) as exc:
        orders.save(draft)
    assert "Недостаточно «Роза красная»" in db.error_text(exc.value)
    # первый букет уже был вставлен в транзакции — откатилось всё
    assert (orders_count(), stock("Роза красная"), stock("Эвкалипт")) == (before_orders, before_rose, before_euc)


# --- страницы -------------------------------------------------------------

def text(response):
    return response.get_data(as_text=True)


def test_new_order_page(client):
    page = text(client.get("/orders/new"))
    assert "Оформление заказа" in page and "Букет 1" in page and 'name="b_count" value="1"' in page


def test_form_add_bouquet_keeps_fields(client, ids):
    page = text(client.post("/orders/new", data={
        "client": ids["client"], "florist": ids["florist"], "payment": "перевод", "b_count": "1",
        "b0_complexity": "сложный", "b0_minutes": "40", "b0_plant": str(plant("Эвкалипт")), "b0_qty": "3",
        "action": "add_bouquet"}))
    assert 'name="b_count" value="2"' in page and "Букет 2" in page
    assert f'<option value="{ids["client"]}" selected' in page
    assert '<option selected>перевод</option>' in page and '<option selected>сложный</option>' in page
    assert 'value="40"' in page and 'value="3"' in page


def test_form_save_error_keeps_form(client, ids):
    page = text(client.post("/orders/new", data={
        "client": ids["client"], "florist": ids["florist"], "payment": "карта", "b_count": "1",
        "b0_complexity": "простой", "b0_minutes": "", "b0_plant": str(plant("Эвкалипт")), "b0_qty": "2",
        "action": "save"}))
    assert "Букет 1: укажите время сборки" in page and 'value="2"' in page


def test_form_save_and_view(client, ids):
    before = orders_count()
    response = client.post("/orders/new", data={
        "client": ids["client"], "florist": ids["florist"], "payment": "карта", "courier": "", "b_count": "1",
        "b0_template": str(ids["template"]), "b0_complexity": "средний", "b0_minutes": "30",
        "p_plant": str(plant("Эвкалипт")), "p_qty": "2", "action": "save"})
    assert response.status_code == 302 and orders_count() == before + 1
    page = text(client.get(response.headers["Location"]))
    assert "оформлен" in page and "Букет 1" in page and "рекомендуемая цена" in page
    assert "самовывоз" in page and "Отдельные растения" in page and "Эвкалипт" in page


def test_order_view_404(client):
    assert client.get("/orders/999999").status_code == 404
