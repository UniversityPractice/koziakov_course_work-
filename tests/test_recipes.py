"""Книга рецептов: шаблоны флориста и их состав."""
from decimal import Decimal

import pytest

import db
import sql


def one(query, params=None):
    return db.fetch_value(query, params)


def text(response):
    return response.get_data(as_text=True)


@pytest.fixture
def florist():
    return one("select id from сотрудники where фио = 'Иванова Анна Сергеевна'")


def plant(name):
    return one("select id from растения where название = %s", (name,))


@pytest.fixture
def template(client, florist):
    """Новый шаблон флориста, созданный через страницу."""
    response = client.post("/recipes/new", data={"florist": florist, "name": "Тестовый рецепт"})
    assert response.status_code == 302
    return int(response.headers["Location"].rsplit("/", 1)[1])


def composition(template_id):
    return dict(db.fetch("select растение_id, количество from состав_шаблона where шаблон_id = %s",
                         (template_id,))[1])


def test_recipes_page_default_and_selected_florist(client, florist):
    assert client.get("/recipes").status_code == 200
    page = text(client.get("/recipes", query_string={"florist": florist}))
    assert "Классика" in page and "1600.00" in page         # пример из раздела 3.2
    assert "Книга рецептов" in page


def test_recipes_list_counts_sold_bouquets(florist):
    rows = db.fetch(sql.TEMPLATE_LIST, (florist,))[1]
    sold = {r[1]: r[5] for r in rows}
    assert sold["Классика"] == one("select count(*) from букеты б join шаблоны ш on ш.id = б.шаблон_id "
                                   "where ш.название = 'Классика'")


def test_create_requires_name(client, florist):
    page = text(client.post("/recipes/new", data={"florist": florist, "name": "  "}, follow_redirects=True))
    assert "Введите название" in page


def test_composition_add_update_delete(client, template):
    rose, eucalyptus = plant("Роза красная"), plant("Эвкалипт")
    assert "В шаблоне пока нет растений" in text(client.get(f"/recipes/{template}"))

    client.post(f"/recipes/{template}/items", data={"plant": rose, "qty": "7"})
    client.post(f"/recipes/{template}/items", data={"plant": eucalyptus, "qty": "3"})
    assert composition(template) == {rose: 7, eucalyptus: 3}
    page = text(client.get(f"/recipes/{template}"))
    assert "1600.00" in page                               # 7 × 95 × 2 + 3 × 60 × 1,5

    client.post(f"/recipes/{template}/items/{rose}", data={"qty": "9"})
    client.post(f"/recipes/{template}/items/{eucalyptus}/delete")
    assert composition(template) == {rose: 9}


def test_duplicate_plant_gives_clear_message(client, template):
    rose = plant("Роза красная")
    client.post(f"/recipes/{template}/items", data={"plant": rose, "qty": "1"})
    page = text(client.post(f"/recipes/{template}/items", data={"plant": rose, "qty": "2"},
                            follow_redirects=True))
    assert "уже есть в шаблоне" in page
    assert composition(template) == {rose: 1}


@pytest.mark.parametrize("data", [{"plant": "", "qty": "2"}, {"plant": "1", "qty": "0"}])
def test_add_item_validation(client, template, data):
    page = text(client.post(f"/recipes/{template}/items", data=data, follow_redirects=True))
    assert "Выберите растение" in page and composition(template) == {}


def test_update_qty_validation(client, template):
    rose = plant("Роза красная")
    client.post(f"/recipes/{template}/items", data={"plant": rose, "qty": "4"})
    page = text(client.post(f"/recipes/{template}/items/{rose}", data={"qty": "0"}, follow_redirects=True))
    assert "больше нуля" in page and composition(template) == {rose: 4}


def test_rename(client, template):
    client.post(f"/recipes/{template}/rename", data={"name": "Осенний вальс"})
    assert one("select название from шаблоны where id = %s", (template,)) == "Осенний вальс"
    page = text(client.post(f"/recipes/{template}/rename", data={"name": ""}, follow_redirects=True))
    assert "Введите название" in page


def test_delete_keeps_sold_bouquets(client, florist):
    """Удаление шаблона: состав удаляется, проданные букеты становятся индивидуальными."""
    template_id = one("""select ш.id from шаблоны ш where ш.флорист_id = %s
                         and exists (select 1 from букеты where шаблон_id = ш.id) order by ш.id limit 1""",
                      (florist,))
    bouquets = [r[0] for r in db.fetch("select id from букеты where шаблон_id = %s", (template_id,))[1]]
    assert "станут индивидуальными" in text(client.get(f"/recipes/{template_id}"))

    page = text(client.post(f"/recipes/{template_id}/delete", follow_redirects=True))
    assert "Шаблон удалён" in page
    assert one("select count(*) from шаблоны where id = %s", (template_id,)) == 0
    assert composition(template_id) == {}
    assert one("select count(*) from букеты where id = any(%s) and шаблон_id is null", (bouquets,)) \
        == len(bouquets) > 0


def test_unknown_recipe_404(client):
    assert client.get("/recipes/999999").status_code == 404
    assert client.post("/recipes/999999/rename", data={"name": "x"}).status_code == 404
