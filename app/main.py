"""Локальный сайт «Флористический центр» (Flask): справочники, заявки, отчёты.

Запуск: python app/main.py, затем открыть http://localhost:8000.
SQL — только в sql.py, работа с БД — только через db.py.
"""
import os
from datetime import date, datetime
from xml.dom import minidom

import psycopg2
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for

import db
import sql
from directories import DIRECTORIES, ORDER_STATUSES, REQUEST_STATUSES, directory, parse_form

app = Flask(__name__)
app.secret_key = "florist-local"  # нужен только для flash-сообщений на локальном сайте

# Отчёты: номер → (название, SQL, параметры: None / "period" / "period_required")
REPORTS = {
    1: ("ТОП-10 растений в букетах за прошлый квартал", sql.REPORT_1, None),
    2: ("Себестоимость и наценка проданных букетов", sql.REPORT_2, "period"),
    3: ("Выручка и число заказов по флористам", sql.REPORT_3, "period_required"),
    4: ("Растения ниже критического остатка", sql.REPORT_4, None),
    5: ("Сезонность: заказы по месяцам прошлого года", sql.REPORT_5, None),
    6: ("Прайс-лист в XML", sql.REPORT_6, None),
    7: ("Среднее время сборки букета по сложности", sql.REPORT_7, None),
}


@app.template_filter("fmt")
def fmt(value):
    """Значение из БД в текст для таблицы."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


@app.context_processor
def menu():
    return {"directories": DIRECTORIES, "reports": REPORTS}


@app.before_request
def ensure_connection():
    """Одно соединение на сайт; если база перезапускалась — подключаемся заново."""
    if db.conn is None or db.conn.closed:
        db.connect()


@app.errorhandler(psycopg2.OperationalError)
def no_connection(e):
    p = db.read_config()
    return render_template("error.html", title="Нет подключения к БД",
                           text=f"Не удалось подключиться к БД {p['host']}:{p['port']}/{p['dbname']}: "
                                f"{db.error_text(e)}"), 503


@app.errorhandler(psycopg2.Error)
def db_error(e):
    return render_template("error.html", title="Ошибка БД", text=db.error_text(e)), 500


@app.route("/")
def index():
    return redirect(url_for("directory_list", slug=DIRECTORIES[0]["slug"]))


# --- Справочники -----------------------------------------------------

def get_directory(slug):
    config = directory(slug)
    if config is None:
        abort(404)
    return config


@app.route("/d/<slug>")
def directory_list(slug):
    config = get_directory(slug)
    columns, rows = db.fetch(config["list"])
    hidden = {0, config["highlight_col"]}  # id и служебный признак не показываем
    visible = [i for i in range(len(columns)) if i not in hidden]
    return render_template("directory.html", config=config, columns=columns, rows=rows, visible=visible)


def form_fields(config, values):
    """Поля для шаблона формы: подпись, вид, варианты выбора, текущее значение."""
    fields = []
    for i, (label, kind, extra, required) in enumerate(config["fields"]):
        if kind == "choice":
            options = [(v, v) for v in extra]
        elif kind == "ref":
            options = db.fetch(extra)[1]
        else:
            options = None
        fields.append({"name": f"f{i}", "label": label, "kind": kind, "required": required,
                       "options": options, "value": "" if values[i] is None else str(values[i])})
    return fields


@app.route("/d/<slug>/new", methods=["GET", "POST"])
@app.route("/d/<slug>/<int:record_id>", methods=["GET", "POST"])
def directory_form(slug, record_id=None):
    config = get_directory(slug)
    error = None
    if request.method == "POST":
        values, error = parse_form(config, request.form)
        if error is None:
            try:
                if record_id is None:
                    db.execute(config["insert"], values)
                else:
                    db.execute(config["update"], values + (record_id,))
            except psycopg2.Error as e:
                error = db.error_text(e)
            else:
                flash("Сохранено.", "ok")
                return redirect(url_for("directory_list", slug=slug))
        # ошибка — показываем форму снова с тем, что ввёл пользователь
        values = [request.form.get(f"f{i}") for i in range(len(config["fields"]))]
    elif record_id is None:
        values = [None] * len(config["fields"])
    else:
        rows = db.fetch(config["get"], (record_id,))[1]
        if not rows:
            abort(404)
        values = rows[0]
    return render_template("form.html", config=config, record_id=record_id, error=error,
                           fields=form_fields(config, values))


@app.post("/d/<slug>/<int:record_id>/delete")
def directory_delete(slug, record_id):
    config = get_directory(slug)
    try:
        db.execute(config["delete"], (record_id,))
        flash("Удалено.", "ok")
    except psycopg2.Error as e:
        flash(db.error_text(e), "error")
    return redirect(url_for("directory_list", slug=slug))


# --- Заказы -----------------------------------------------------------

# Кнопка на странице → новый статус заказа
ORDER_ACTIONS = {
    "delivery": ("в доставке", "Передать курьеру", "Заказ передан курьеру."),
    "delivered": ("вручён", "Вручён", "Заказ вручён."),
    "failed": ("не вручён", "Не вручён", "Отмечено: заказ не вручён."),
}
# Какие кнопки показывать в каждом статусе (проверяет всё равно триггер в БД)
ORDER_BUTTONS = {
    "принят": ["delivery", "delivered", "cancel"],
    "в доставке": ["delivered", "failed"],
    "не вручён": ["delivery", "delivered"],
    "вручён": [],
}
ORDER_FILTERS = ["активные"] + ORDER_STATUSES + ["все"]


@app.route("/orders")
def orders_list():
    current = request.args.get("status", "активные")
    if current not in ORDER_FILTERS:
        current = "активные"
    columns, rows = db.fetch(sql.ORDER_LIST, {"фильтр": current})
    return render_template("orders.html", columns=columns, rows=rows, current=current,
                           filters=ORDER_FILTERS, actions=ORDER_ACTIONS, buttons=ORDER_BUTTONS)


@app.post("/orders/<int:order_id>/<action>")
def orders_action(order_id, action):
    try:
        if action == "cancel":
            db.execute(sql.ORDER_DELETE, (order_id,))
            flash("Заказ отменён, растения вернулись на склад.", "ok")
        elif action in ORDER_ACTIONS:
            status, _, done = ORDER_ACTIONS[action]
            db.execute(sql.ORDER_SET_STATUS, (status, order_id))
            flash(done, "ok")
        else:
            abort(404)
    except psycopg2.Error as e:
        flash(db.error_text(e), "error")
    return redirect(url_for("orders_list", status=request.args.get("status", "активные")))


# --- Заявки на закупку -------------------------------------------------

@app.route("/requests")
def requests_list():
    status = request.args.get("status", "новая")
    columns, rows = db.fetch(sql.REQUEST_LIST, {"статус": status if status in REQUEST_STATUSES else None})
    return render_template("requests.html", columns=columns, rows=rows,
                           status=status, statuses=REQUEST_STATUSES)


@app.post("/requests/generate")
def requests_generate():
    before = db.fetch_value(sql.REQUEST_COUNT)
    db.execute(sql.REQUEST_GENERATE)
    added = db.fetch_value(sql.REQUEST_COUNT) - before
    flash(f"Добавлено заявок: {added}." if added else "Новых заявок не нужно: запасов хватает.", "ok")
    return redirect(url_for("requests_list"))


@app.post("/requests/<int:request_id>/<action>")
def requests_set_status(request_id, action):
    status = {"received": "выполнена", "cancel": "отменена"}.get(action)
    if status is None:
        abort(404)
    try:
        db.execute(sql.REQUEST_SET_STATUS, (status, request_id))
        flash("Товар получен, склад пополнен." if status == "выполнена" else "Заявка отменена.", "ok")
    except psycopg2.Error as e:
        flash(db.error_text(e), "error")
    return redirect(url_for("requests_list", status=request.args.get("status", "новая")))


# --- Отчёты -----------------------------------------------------------

def report_params(kind):
    """Параметры периода из адреса страницы: {"с": ..., "по": ...}."""
    if kind is None:
        return None
    start, end = request.args.get("from") or None, request.args.get("to") or None
    if kind == "period_required":
        today = date.today()
        start = start or today.replace(month=1, day=1).isoformat()
        end = end or today.isoformat()
    return {"с": start, "по": end}


def run_report(n):
    title, query, kind = REPORTS[n]
    params = report_params(kind)
    columns, rows = db.fetch(query, params)
    return title, kind, params, columns, rows


@app.route("/reports/<int:n>")
def report(n):
    if n not in REPORTS:
        abort(404)
    title, kind, params, columns, rows = run_report(n)
    xml = minidom.parseString(rows[0][0]).toprettyxml(indent="  ") if n == 6 else None
    return render_template("report.html", n=n, title=title, kind=kind, params=params,
                           columns=columns, rows=rows, xml=xml)


@app.route("/reports/6/price.xml")
def report_xml():
    xml = minidom.parseString(db.fetch_value(sql.REPORT_6)).toprettyxml(indent="  ", encoding="utf-8")
    return Response(xml, mimetype="application/xml",
                    headers={"Content-Disposition": "attachment; filename=price.xml"})


if __name__ == "__main__":
    # threaded=False: запросы обрабатываются по очереди, одного соединения хватает
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
            threaded=False)
