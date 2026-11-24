"""Справочники: категории, поставщики, растения, сотрудники, клиенты, списания.

Все шесть страниц устроены одинаково: таблица из запроса list и форма
добавления/изменения. Чем справочники отличаются (SQL-запросы и поля формы),
описано словарями в списке DIRECTORIES.

Поле формы — кортеж (подпись, вид, доп. данные, обязательное):
    text   — строка (пустая строка сохраняется как NULL);
    int    — целое, доп. данные — (минимум, максимум);
    money  — число с 2 знаками;
    choice — выпадающий список, доп. данные — допустимые значения;
    ref    — выпадающий список из БД, доп. данные — SQL (id, подпись).
В HTML-форме поля называются f0, f1, ... по порядку.
"""
from decimal import Decimal, InvalidOperation

import sql

# Допустимые значения из ограничений CHECK схемы БД
PLANT_TYPES = ["срезанный", "горшечный"]
POSITIONS = ["флорист", "курьер"]
WRITEOFF_REASONS = ["увядание", "брак", "повреждение"]
REQUEST_STATUSES = ["новая", "выполнена", "отменена"]

DIRECTORIES = [
    {
        "slug": "plants", "title": "Растения",
        "list": sql.PLANT_LIST, "get": sql.PLANT_GET, "insert": sql.PLANT_INSERT,
        "update": sql.PLANT_UPDATE, "delete": sql.PLANT_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Тип", "choice", PLANT_TYPES, True),
                   ("Категория", "ref", sql.CATEGORIES_LOOKUP, True),
                   ("Поставщик", "ref", sql.SUPPLIERS_LOOKUP, True),
                   ("Закупочная цена", "money", None, True),
                   ("Остаток", "int", (0, 1_000_000), True),
                   ("Мин. остаток", "int", (0, 1_000_000), True)],
        "highlight_col": 9,  # «остаток ниже минимума» — строка подсвечивается
        "delete_question": "Удалить растение?",
    },
    {
        "slug": "categories", "title": "Категории",
        "list": sql.CATEGORY_LIST, "get": sql.CATEGORY_GET, "insert": sql.CATEGORY_INSERT,
        "update": sql.CATEGORY_UPDATE, "delete": sql.CATEGORY_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Коэф. наценки", "money", None, True)],
        "highlight_col": None,
        "delete_question": "Удалить категорию?",
    },
    {
        "slug": "suppliers", "title": "Поставщики",
        "list": sql.SUPPLIER_LIST, "get": sql.SUPPLIER_GET, "insert": sql.SUPPLIER_INSERT,
        "update": sql.SUPPLIER_UPDATE, "delete": sql.SUPPLIER_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Телефон", "text", None, False),
                   ("Срок поставки, дн.", "int", (1, 365), True)],
        "highlight_col": None,
        "delete_question": "Удалить поставщика?",
    },
    {
        "slug": "employees", "title": "Сотрудники",
        "list": sql.EMPLOYEE_LIST, "get": sql.EMPLOYEE_GET, "insert": sql.EMPLOYEE_INSERT,
        "update": sql.EMPLOYEE_UPDATE, "delete": sql.EMPLOYEE_DELETE,
        "fields": [("ФИО", "text", None, True),
                   ("Должность", "choice", POSITIONS, True),
                   ("Телефон", "text", None, False)],
        "highlight_col": None,
        "delete_question": "Удалить сотрудника?",
    },
    {
        "slug": "clients", "title": "Клиенты",
        "list": sql.CLIENT_LIST, "get": sql.CLIENT_GET, "insert": sql.CLIENT_INSERT,
        "update": sql.CLIENT_UPDATE, "delete": sql.CLIENT_DELETE,
        "fields": [("Имя", "text", None, True),
                   ("Телефон", "text", None, False),
                   ("Email", "text", None, False)],
        "highlight_col": None,
        "delete_question": "Удалить клиента?",
    },
    {
        "slug": "writeoffs", "title": "Списания",
        "list": sql.WRITEOFF_LIST, "get": sql.WRITEOFF_GET, "insert": sql.WRITEOFF_INSERT,
        "update": sql.WRITEOFF_UPDATE, "delete": sql.WRITEOFF_DELETE,
        "fields": [("Растение", "ref", sql.PLANTS_LOOKUP, True),
                   ("Количество", "int", (1, 100_000), True),
                   ("Причина", "choice", WRITEOFF_REASONS, True)],
        "highlight_col": None,
        "delete_question": "Отменить списание? Растения вернутся на склад.",
    },
]


def directory(slug):
    """Настройки справочника по адресу страницы или None."""
    return next((config for config in DIRECTORIES if config["slug"] == slug), None)


def parse_form(config, form):
    """Значения из HTML-формы в порядке fields (для параметров INSERT/UPDATE).

    Возвращает (значения, текст ошибки). Если ошибки нет, текст — None.
    """
    values = []
    for i, (label, kind, extra, required) in enumerate(config["fields"]):
        raw = (form.get(f"f{i}") or "").strip()
        if not raw:
            if required:
                return None, f"Заполните поле «{label}»."
            values.append(None)
            continue
        try:
            if kind == "int":
                value = int(raw)
                if not extra[0] <= value <= extra[1]:
                    return None, f"Поле «{label}»: от {extra[0]} до {extra[1]}."
            elif kind == "money":
                value = Decimal(raw.replace(",", ".")).quantize(Decimal("0.01"))
            elif kind == "ref":
                value = int(raw)
            else:  # text, choice — проверку choice делает CHECK в базе
                value = raw
        except (ValueError, InvalidOperation):
            return None, f"Поле «{label}»: неверное число."
        values.append(value)
    return tuple(values), None
