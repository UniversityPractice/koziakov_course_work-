"""Оформление заказа: черновик из HTML-формы, пересчёт цен и сохранение.

Форма работает без JavaScript-логики: каждая кнопка («Добавить букет»,
«Пересчитать», выбор шаблона) отправляет форму на сервер, сервер читает
черновик (read_draft), выполняет действие (apply_action), пересчитывает
цены SQL-запросами (recalc) и показывает форму снова. «Оформить заказ»
проверяет черновик (check) и сохраняет его одной транзакцией (save).

Черновик — словарь:
    client, florist, courier — id или None; payment — способ оплаты;
    address, time, recipient, recipient_phone — строки;
    bouquets — список букетов: template (id или None), complexity, minutes,
        price (строка из формы), rec (рекомендуемая цена), items [(растение_id, кол)];
    plants — отдельные растения [(растение_id, кол)].
"""
from decimal import Decimal, InvalidOperation

import db
import sql

PAYMENT_METHODS = ["наличные", "карта", "перевод"]
COMPLEXITIES = ["простой", "средний", "сложный"]


def to_int(raw):
    """Положительное целое из строки формы или None."""
    try:
        value = int((raw or "").strip())
    except ValueError:
        return None
    return value if value > 0 else None


def to_money(raw):
    """Неотрицательная сумма из строки формы (запятая допустима) или None."""
    try:
        value = Decimal((raw or "").strip().replace(",", ".")).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def read_items(plants, quantities):
    """Пары (растение, количество) из двух списков полей формы.

    Пустые и неверные строки пропускаются, одно растение дважды — количества складываются.
    """
    merged = {}
    for plant, qty in zip(plants, quantities):
        plant, qty = to_int(plant), to_int(qty)
        if plant and qty:
            merged[plant] = merged.get(plant, 0) + qty
    return list(merged.items())


def empty_bouquet():
    return {"template": None, "complexity": COMPLEXITIES[0], "minutes": "", "price": "",
            "rec": None, "items": []}


def empty_draft():
    return {"client": None, "florist": None, "payment": PAYMENT_METHODS[0], "courier": None,
            "address": "", "time": "", "recipient": "", "recipient_phone": "",
            "bouquets": [], "plants": []}


def read_draft(form):
    """Черновик заказа из полей формы."""
    draft = {
        "client": to_int(form.get("client")),
        "florist": to_int(form.get("florist")),
        "payment": form.get("payment", PAYMENT_METHODS[0]),
        "courier": to_int(form.get("courier")),
        "address": form.get("address", "").strip(),
        "time": form.get("time", "").strip(),
        "recipient": form.get("recipient", "").strip(),
        "recipient_phone": form.get("recipient_phone", "").strip(),
        "bouquets": [],
        "plants": read_items(form.getlist("p_plant"), form.getlist("p_qty")),
    }
    for i in range(to_int(form.get("b_count")) or 0):
        p = f"b{i}_"
        draft["bouquets"].append({
            "template": to_int(form.get(p + "template")),
            "complexity": form.get(p + "complexity", COMPLEXITIES[0]),
            "minutes": form.get(p + "minutes", "").strip(),
            "price": form.get(p + "price", "").strip(),
            "rec": to_money(form.get(p + "rec")),
            "items": read_items(form.getlist(p + "plant"), form.getlist(p + "qty")),
        })
    return draft


def template_items(template_id):
    return [tuple(row) for row in db.fetch(sql.TEMPLATE_ITEMS, (template_id,))[1]]


def apply_action(draft, action):
    """Действие кнопки: add_bouquet, remove:N (удалить букет N), template:N (взять состав шаблона)."""
    if action == "add_bouquet":
        draft["bouquets"].append(empty_bouquet())
        return
    name, _, number = action.partition(":")
    if not number.isdigit() or int(number) >= len(draft["bouquets"]):
        return
    i = int(number)
    if name == "remove":
        del draft["bouquets"][i]
    elif name == "template":
        bouquet = draft["bouquets"][i]
        bouquet["items"] = template_items(bouquet["template"]) if bouquet["template"] else []


def recalc(draft):
    """Рекомендуемые цены букетов и итог заказа (считает база).

    Цена продажи букета следует за рекомендуемой, пока её не изменили вручную.
    Шаблон чужого флориста сбрасывается в «индивидуальный», состав остаётся.
    """
    florist_templates = set()
    if draft["florist"]:
        florist_templates = {t for t, _ in db.fetch(sql.FLORIST_TEMPLATES_LOOKUP, (draft["florist"],))[1]}
    for b in draft["bouquets"]:
        if b["template"] not in florist_templates:
            b["template"] = None
        if b["template"] and not b["items"]:
            b["items"] = template_items(b["template"])
        plants = [plant for plant, _ in b["items"]]
        quantities = [qty for _, qty in b["items"]]
        rec = db.fetch_value(sql.DRAFT_RECOMMENDED_PRICE, (plants, quantities))
        if not b["price"] or to_money(b["price"]) == b["rec"]:
            b["price"] = str(rec)
        b["rec"] = rec

    retail = dict(db.fetch(sql.PLANT_RETAIL_PRICES, ([plant for plant, _ in draft["plants"]],))[1])
    draft["plant_prices"] = {plant: retail[plant] * qty for plant, qty in draft["plants"]}
    bouquets_total = sum((to_money(b["price"]) or 0 for b in draft["bouquets"]), Decimal(0))
    draft["total"] = bouquets_total + sum(draft["plant_prices"].values(), Decimal(0))
    return draft


def check(draft):
    """Проверки до отправки в БД (раздел 6.5 плана). Текст ошибки или None."""
    if not draft["client"]:
        return "Выберите клиента."
    if not draft["florist"]:
        return "Выберите флориста."
    if draft["payment"] not in PAYMENT_METHODS:
        return "Выберите способ оплаты."
    if draft["courier"] and not draft["address"]:
        return "Для доставки укажите адрес."
    if not draft["bouquets"] and not draft["plants"]:
        return "Добавьте в заказ букет или растение."
    for n, b in enumerate(draft["bouquets"], start=1):
        if not b["items"]:
            return f"В букете {n} нет ни одного растения."
        if b["complexity"] not in COMPLEXITIES:
            return f"Букет {n}: выберите сложность."
        if not to_int(b["minutes"]):
            return f"Букет {n}: укажите время сборки в минутах."
        if to_money(b["price"]) is None:
            return f"Букет {n}: неверная цена продажи."
    return None


def save(draft):
    """Сохраняет заказ одной транзакцией и возвращает его id.

    Остатки проверяет и уменьшает триггер тр_склад: если чего-то не хватает,
    транзакция откатывается целиком и исключение передаётся дальше.
    """
    delivery = draft["courier"] is not None
    with db.transaction() as cur:
        cur.execute(sql.ORDER_INSERT, (
            draft["client"], draft["florist"], draft["payment"], draft["courier"],
            draft["address"] if delivery else None,
            (draft["time"] or None) if delivery else None,
            (draft["recipient"] or None) if delivery else None,
            (draft["recipient_phone"] or None) if delivery else None))
        order_id = cur.fetchone()[0]
        for b in draft["bouquets"]:
            cur.execute(sql.BOUQUET_INSERT, (order_id, b["template"], b["complexity"],
                                             to_int(b["minutes"]), to_money(b["price"])))
            bouquet_id = cur.fetchone()[0]
            for plant, qty in b["items"]:
                cur.execute(sql.BOUQUET_ITEM_INSERT, (bouquet_id, plant, qty))
        for plant, qty in draft["plants"]:
            cur.execute(sql.ORDER_PLANT_INSERT, (order_id, plant, qty))
    return order_id
