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
import orders
import sql
from directories import DIRECTORIES, ORDER_STATUSES, REQUEST_STATUSES, directory, parse_form

app = Flask(__name__)
app.secret_key = "florist-local"  # нужен только для flash-сообщений на локальном сайте
app.json.ensure_ascii = False      # tojson в шаблонах оставляет кириллицу читаемой

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
    db.ensure_connection()


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


@app.route("/orders/new", methods=["GET", "POST"])
def order_new():
    """Оформление заказа: каждая кнопка формы присылает черновик сюда же."""
    error = None
    action = request.form.get("action", "recalc")
    if request.method == "GET":
        draft = orders.empty_draft()
        draft["bouquets"].append(orders.empty_bouquet())
    else:
        draft = orders.read_draft(request.form)
        orders.apply_action(draft, action)
    orders.recalc(draft)

    if request.method == "POST" and action == "save":
        error = orders.check(draft)
        if error is None:
            try:
                order_id = orders.save(draft)
            except psycopg2.Error as e:
                error = db.error_text(e)  # транзакция откатилась, форма остаётся заполненной
            else:
                flash(f"Заказ №{order_id} оформлен.", "ok")
                return redirect(url_for("order_view", order_id=order_id))

    templates = db.fetch(sql.FLORIST_TEMPLATES_LOOKUP, (draft["florist"],))[1] if draft["florist"] else []
    return render_template("order_form.html", draft=draft, error=error, templates=templates,
                           clients=db.fetch(sql.CLIENTS_LOOKUP)[1],
                           florists=db.fetch(sql.FLORISTS_LOOKUP)[1],
                           couriers=db.fetch(sql.COURIERS_LOOKUP)[1],
                           plants=db.fetch(sql.PLANTS_LOOKUP)[1],
                           payments=orders.PAYMENT_METHODS, complexities=orders.COMPLEXITIES)


@app.route("/orders/<int:order_id>")
def order_view(order_id):
    rows = db.fetch(sql.ORDER_GET, (order_id,))[1]
    if not rows:
        abort(404)
    bouquet_columns, bouquets = db.fetch(sql.ORDER_BOUQUETS, (order_id,))
    item_columns, items = db.fetch(sql.ORDER_BOUQUET_ITEMS, (order_id,))
    plant_columns, plants = db.fetch(sql.ORDER_PLANTS, (order_id,))
    return render_template("order_view.html", order=rows[0], buttons=ORDER_BUTTONS, actions=ORDER_ACTIONS,
                           bouquet_columns=bouquet_columns, bouquets=bouquets,
                           item_columns=item_columns, items=items,
                           plant_columns=plant_columns, plants=plants)


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


# --- Книга рецептов -----------------------------------------------------

def get_recipe(template_id):
    rows = db.fetch(sql.TEMPLATE_GET, (template_id,))[1]
    if not rows:
        abort(404)
    return rows[0]


def back_to_recipe(template_id):
    return redirect(url_for("recipe_view", template_id=template_id))


@app.route("/recipes")
def recipes_list():
    florists = db.fetch(sql.FLORISTS_LOOKUP)[1]
    florist = orders.to_int(request.args.get("florist"))
    if florist not in {fid for fid, _ in florists}:
        florist = florists[0][0] if florists else None
    columns, rows = db.fetch(sql.TEMPLATE_LIST, (florist,)) if florist else ([], [])
    return render_template("recipes.html", florists=florists, florist=florist, columns=columns, rows=rows)


@app.post("/recipes/new")
def recipe_new():
    florist = orders.to_int(request.form.get("florist"))
    name = request.form.get("name", "").strip()
    if not name:
        flash("Введите название шаблона.", "error")
        return redirect(url_for("recipes_list", florist=florist))
    try:
        template_id = db.execute(sql.TEMPLATE_INSERT, (florist, name))
    except psycopg2.Error as e:
        flash(db.error_text(e), "error")
        return redirect(url_for("recipes_list", florist=florist))
    flash("Шаблон создан. Добавьте в него растения.", "ok")
    return back_to_recipe(template_id)


@app.route("/recipes/<int:template_id>")
def recipe_view(template_id):
    recipe = get_recipe(template_id)
    columns, rows = db.fetch(sql.TEMPLATE_COMPOSITION, (template_id,))
    delete_question = f"Удалить шаблон «{recipe[1]}»?"
    if recipe[5]:
        delete_question += f" Проданные по нему букеты ({recipe[5]}) останутся и станут индивидуальными."
    return render_template("recipe.html", recipe=recipe, columns=columns, rows=rows,
                           plants=db.fetch(sql.PLANTS_LOOKUP)[1], delete_question=delete_question)


@app.post("/recipes/<int:template_id>/rename")
def recipe_rename(template_id):
    get_recipe(template_id)
    name = request.form.get("name", "").strip()
    if not name:
        flash("Введите название шаблона.", "error")
    else:
        db.execute(sql.TEMPLATE_RENAME, (name, template_id))
        flash("Шаблон переименован.", "ok")
    return back_to_recipe(template_id)


@app.post("/recipes/<int:template_id>/delete")
def recipe_delete(template_id):
    florist = get_recipe(template_id)[2]
    db.execute(sql.TEMPLATE_DELETE, (template_id,))
    flash("Шаблон удалён. Проданные по нему букеты остались и стали индивидуальными.", "ok")
    return redirect(url_for("recipes_list", florist=florist))


@app.post("/recipes/<int:template_id>/items")
def recipe_item_add(template_id):
    get_recipe(template_id)
    plant, qty = orders.to_int(request.form.get("plant")), orders.to_int(request.form.get("qty"))
    if not plant or not qty:
        flash("Выберите растение и укажите количество больше нуля.", "error")
        return back_to_recipe(template_id)
    try:
        db.execute(sql.TEMPLATE_ITEM_INSERT, (template_id, plant, qty))
        flash("Растение добавлено.", "ok")
    except psycopg2.Error as e:
        # повтор растения — нарушение первичного ключа (шаблон, растение)
        flash("Это растение уже есть в шаблоне — измените его количество в таблице."
              if e.pgcode == "23505" else db.error_text(e), "error")
    return back_to_recipe(template_id)


@app.post("/recipes/<int:template_id>/items/<int:plant_id>")
def recipe_item_update(template_id, plant_id):
    get_recipe(template_id)
    qty = orders.to_int(request.form.get("qty"))
    if not qty:
        flash("Количество должно быть больше нуля. Чтобы убрать растение, нажмите «Удалить».", "error")
    else:
        db.execute(sql.TEMPLATE_ITEM_UPDATE, (qty, template_id, plant_id))
        flash("Количество изменено.", "ok")
    return back_to_recipe(template_id)


@app.post("/recipes/<int:template_id>/items/<int:plant_id>/delete")
def recipe_item_delete(template_id, plant_id):
    get_recipe(template_id)
    db.execute(sql.TEMPLATE_ITEM_DELETE, (template_id, plant_id))
    flash("Растение убрано из шаблона.", "ok")
    return back_to_recipe(template_id)


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
