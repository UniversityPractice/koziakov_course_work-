"""Страницы сайта: открываются, формы сохраняют, ошибки БД показываются понятно."""
import psycopg2
import pytest

import db
from conftest import TEST_PARAMS
import sql
from directories import DIRECTORIES


def stock(name):
    return db.fetch_value("select остаток from растения where название = %s", (name,))


def text(response):
    return response.get_data(as_text=True)


def test_index_redirects(client):
    assert client.get("/").status_code == 302


@pytest.mark.parametrize("cfg", DIRECTORIES, ids=lambda c: c["slug"])
def test_directory_pages_open(client, cfg):
    page = client.get(f"/d/{cfg['slug']}")
    assert page.status_code == 200 and cfg["title"] in text(page)
    assert client.get(f"/d/{cfg['slug']}/new").status_code == 200
    first_id = db.fetch(cfg["list"])[1][0][0]
    assert client.get(f"/d/{cfg['slug']}/{first_id}").status_code == 200


def test_reconnects_after_db_restart(client):
    """Соединение оборвалось (база перезапускалась) — сайт подключается заново, без ошибки."""
    old = db.conn
    killer = psycopg2.connect(**TEST_PARAMS)
    killer.autocommit = True
    with killer.cursor() as c:
        c.execute("select pg_terminate_backend(%s)", (old.get_backend_pid(),))
    killer.close()
    assert client.get("/d/categories").status_code == 200
    assert db.conn is not old and "dbname=florist_test" in db.conn.dsn


def test_unknown_pages_404(client):
    assert client.get("/d/nope").status_code == 404
    assert client.get("/reports/8").status_code == 404


def test_low_stock_rows_highlighted(client):
    assert 'class="low"' in text(client.get("/d/plants"))


def test_add_edit_delete_category(client):
    page = client.post("/d/categories/new", data={"f0": "Веб-кат", "f1": "1.5"}, follow_redirects=True)
    assert "Сохранено" in text(page) and "Веб-кат" in text(page)
    cat_id = db.fetch_value("select id from категории where название = 'Веб-кат'")
    client.post(f"/d/categories/{cat_id}", data={"f0": "Веб-кат", "f1": "1.7"})
    assert str(db.fetch_value("select коэф_наценки from категории where id = %s", (cat_id,))) == "1.70"
    client.post(f"/d/categories/{cat_id}/delete")
    assert db.fetch_value("select count(*) from категории where id = %s", (cat_id,)) == 0


def test_form_shows_validation_and_db_errors(client):
    page = client.post("/d/categories/new", data={"f0": "", "f1": "1.5"})
    assert "Заполните поле «Название»" in text(page)
    page = client.post("/d/categories/new", data={"f0": "Дешёвые", "f1": "0.5"})
    assert "Недопустимое значение" in text(page) and 'value="Дешёвые"' in text(page)


def test_delete_used_record_shows_error(client):
    rose = db.fetch_value("select id from категории where название = 'Розы'")
    page = client.post(f"/d/categories/{rose}/delete", follow_redirects=True)
    assert "используется" in text(page)


def test_requests_flow(client):
    assert client.get("/requests").status_code == 200
    assert client.get("/requests?status=все").status_code == 200
    page = client.post("/requests/generate", follow_redirects=True)
    assert "заяв" in text(page).lower()

    req_id, plant, qty = db.fetch(
        "select з.id, р.название, з.количество from заявки_на_закупку з "
        "join растения р on р.id = з.растение_id where статус = 'новая' order by з.id limit 1")[1][0]
    before = stock(plant)
    page = client.post(f"/requests/{req_id}/received", follow_redirects=True)
    assert "склад пополнен" in text(page)
    assert stock(plant) == before + qty
    # закрытую заявку изменить нельзя — ошибка триггера на странице
    page = client.post(f"/requests/{req_id}/cancel", follow_redirects=True)
    assert "уже закрыта" in text(page)


@pytest.mark.parametrize("n", range(1, 8))
def test_reports_open(client, n):
    page = client.get(f"/reports/{n}")
    assert page.status_code == 200
    assert "Нет данных" not in text(page)


def test_report_3_period_matches_sql(client):
    rows = db.fetch(sql.REPORT_3, {"с": "2026-01-01", "по": "2026-09-30"})[1]
    page = text(client.get("/reports/3?from=2026-01-01&to=2026-09-30"))
    assert all(r[0] in page for r in rows)


def test_report_6_xml_download(client):
    response = client.get("/reports/6/price.xml")
    assert response.status_code == 200
    assert "attachment" in response.headers["Content-Disposition"]
    assert "<прайс_лист>" in response.get_data().decode("utf-8")
