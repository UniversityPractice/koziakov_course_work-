"""Справочники: категории, поставщики, растения, сотрудники, клиенты, списания.

Все шесть вкладок — один класс DirectoryTab. Чем справочники отличаются
(SQL-запросы и поля формы), описано словарями в списке DIRECTORIES.

Поле формы — кортеж (подпись, вид, доп. данные, обязательное):
    text   — строка (пустая строка сохраняется как NULL);
    int    — целое, доп. данные — (минимум, максимум);
    money  — число с 2 знаками;
    choice — выпадающий список, доп. данные — допустимые значения;
    ref    — выпадающий список из БД, доп. данные — SQL (id, подпись).
"""
import psycopg2
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
                             QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QWidget)

import db
import sql
from ui.common import (PLANT_TYPES, POSITIONS, WRITEOFF_REASONS, confirm, fill_table, message,
                       new_table, selected_id, show_error)

LOW_STOCK_COLOR = QColor("#ffd6d6")

DIRECTORIES = [
    {
        "title": "Растения",
        "list": sql.PLANT_LIST, "get": sql.PLANT_GET, "insert": sql.PLANT_INSERT,
        "update": sql.PLANT_UPDATE, "delete": sql.PLANT_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Тип", "choice", PLANT_TYPES, True),
                   ("Категория", "ref", sql.CATEGORIES_LOOKUP, True),
                   ("Поставщик", "ref", sql.SUPPLIERS_LOOKUP, True),
                   ("Закупочная цена", "money", None, True),
                   ("Остаток", "int", (0, 1_000_000), True),
                   ("Мин. остаток", "int", (0, 1_000_000), True)],
        "highlight_col": 9,
        "delete_question": "Удалить растение?",
    },
    {
        "title": "Категории",
        "list": sql.CATEGORY_LIST, "get": sql.CATEGORY_GET, "insert": sql.CATEGORY_INSERT,
        "update": sql.CATEGORY_UPDATE, "delete": sql.CATEGORY_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Коэф. наценки", "money", None, True)],
        "highlight_col": None,
        "delete_question": "Удалить категорию?",
    },
    {
        "title": "Поставщики",
        "list": sql.SUPPLIER_LIST, "get": sql.SUPPLIER_GET, "insert": sql.SUPPLIER_INSERT,
        "update": sql.SUPPLIER_UPDATE, "delete": sql.SUPPLIER_DELETE,
        "fields": [("Название", "text", None, True),
                   ("Телефон", "text", None, False),
                   ("Срок поставки, дн.", "int", (1, 365), True)],
        "highlight_col": None,
        "delete_question": "Удалить поставщика?",
    },
    {
        "title": "Сотрудники",
        "list": sql.EMPLOYEE_LIST, "get": sql.EMPLOYEE_GET, "insert": sql.EMPLOYEE_INSERT,
        "update": sql.EMPLOYEE_UPDATE, "delete": sql.EMPLOYEE_DELETE,
        "fields": [("ФИО", "text", None, True),
                   ("Должность", "choice", POSITIONS, True),
                   ("Телефон", "text", None, False)],
        "highlight_col": None,
        "delete_question": "Удалить сотрудника?",
    },
    {
        "title": "Клиенты",
        "list": sql.CLIENT_LIST, "get": sql.CLIENT_GET, "insert": sql.CLIENT_INSERT,
        "update": sql.CLIENT_UPDATE, "delete": sql.CLIENT_DELETE,
        "fields": [("Имя", "text", None, True),
                   ("Телефон", "text", None, False),
                   ("Email", "text", None, False)],
        "highlight_col": None,
        "delete_question": "Удалить клиента?",
    },
    {
        "title": "Списания",
        "list": sql.WRITEOFF_LIST, "get": sql.WRITEOFF_GET, "insert": sql.WRITEOFF_INSERT,
        "update": sql.WRITEOFF_UPDATE, "delete": sql.WRITEOFF_DELETE,
        "fields": [("Растение", "ref", sql.PLANTS_LOOKUP, True),
                   ("Количество", "int", (1, 100_000), True),
                   ("Причина", "choice", WRITEOFF_REASONS, True)],
        "highlight_col": None,
        "delete_question": "Отменить списание? Растения вернутся на склад.",
    },
]


def directory(title):
    """Настройки справочника по заголовку."""
    return next(config for config in DIRECTORIES if config["title"] == title)


class RecordDialog(QDialog):
    """Форма добавления (record_id=None) или изменения записи справочника.

    По «ОК» сама сохраняет запись в БД. При ошибке БД показывает сообщение
    и остаётся открытой. После сохранения id записи — в self.record_id.
    """

    def __init__(self, parent, config, values=None, record_id=None):
        super().__init__(parent)
        self.config = config
        self.record_id = record_id
        self.setWindowTitle(config["title"] + (": изменение" if record_id else ": добавление"))
        self.setMinimumWidth(420)

        form = QFormLayout(self)
        self.widgets = []
        for label, kind, extra, required in config["fields"]:
            widget = self.make_widget(kind, extra)
            self.widgets.append(widget)
            form.addRow(label + (" *" if required else ""), widget)
        if values is not None:
            self.set_values(values)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def make_widget(kind, extra):
        if kind == "text":
            return QLineEdit()
        if kind == "int":
            widget = QSpinBox()
            widget.setRange(*extra)
            return widget
        if kind == "money":
            widget = QDoubleSpinBox()
            widget.setDecimals(2)
            widget.setRange(0, 10_000_000)
            return widget
        widget = QComboBox()
        if kind == "choice":
            widget.addItems(extra)
        else:  # ref: подписи из БД, id хранится в данных пункта
            for item_id, label in db.fetch(extra)[1]:
                widget.addItem(label, item_id)
        return widget

    def set_values(self, values):
        for (label, kind, extra, required), widget, value in zip(self.config["fields"], self.widgets, values):
            if kind == "text":
                widget.setText(value or "")
            elif kind == "int":
                widget.setValue(value)
            elif kind == "money":
                widget.setValue(float(value))
            elif kind == "choice":
                widget.setCurrentText(value)
            else:
                widget.setCurrentIndex(widget.findData(value))

    def values(self):
        """Значения полей в порядке fields (для параметров INSERT/UPDATE)."""
        result = []
        for (label, kind, extra, required), widget in zip(self.config["fields"], self.widgets):
            if kind == "text":
                result.append(widget.text().strip() or None)
            elif kind == "int":
                result.append(widget.value())
            elif kind == "money":
                result.append(round(widget.value(), 2))
            elif kind == "choice":
                result.append(widget.currentText())
            else:
                result.append(widget.currentData())
        return tuple(result)

    def save(self):
        values = self.values()
        for (label, kind, extra, required), value in zip(self.config["fields"], values):
            if required and value is None:
                message(self, f"Заполните поле «{label}».")
                return
        try:
            if self.record_id is None:
                self.record_id = db.execute(self.config["insert"], values)
            else:
                db.execute(self.config["update"], values + (self.record_id,))
        except psycopg2.Error as e:
            show_error(self, e)
            return
        self.accept()


class DirectoryTab(QWidget):
    """Вкладка справочника: таблица записей и кнопки ввода, изменения, удаления."""

    def __init__(self, config):
        super().__init__()
        self.config = config
        buttons = QHBoxLayout()
        for text, handler in [("Добавить", self.add), ("Изменить", self.edit),
                              ("Удалить", self.delete), ("Обновить", self.refresh)]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            buttons.addWidget(button)
        buttons.addStretch()

        self.table = new_table()
        self.table.doubleClicked.connect(lambda index: self.edit())

        layout = QVBoxLayout(self)
        layout.addLayout(buttons)
        layout.addWidget(self.table)

    def refresh(self):
        try:
            columns, rows = db.fetch(self.config["list"])
        except psycopg2.Error as e:
            show_error(self, e)
            return
        fill_table(self.table, columns, rows)
        col = self.config["highlight_col"]
        if col is not None:
            self.table.setColumnHidden(col, True)
            for r, row in enumerate(rows):
                if row[col]:
                    for c in range(len(columns)):
                        self.table.item(r, c).setBackground(LOW_STOCK_COLOR)

    def add(self):
        if RecordDialog(self, self.config).exec_():
            self.refresh()

    def edit(self):
        record_id = selected_id(self.table)
        if record_id is None:
            message(self, "Выберите запись в таблице.")
            return
        values = db.fetch(self.config["get"], (record_id,))[1][0]
        if RecordDialog(self, self.config, values, record_id).exec_():
            self.refresh()

    def delete(self):
        record_id = selected_id(self.table)
        if record_id is None:
            message(self, "Выберите запись в таблице.")
            return
        if not confirm(self, self.config["delete_question"]):
            return
        try:
            db.execute(self.config["delete"], (record_id,))
        except psycopg2.Error as e:
            show_error(self, e)
        self.refresh()
