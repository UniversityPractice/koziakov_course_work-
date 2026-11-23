"""Общие помощники для экранов: таблицы, сообщения, форматирование значений."""
from datetime import date, datetime

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QAbstractItemView, QMessageBox, QTableWidget, QTableWidgetItem

import db

# Допустимые значения из ограничений CHECK схемы БД
PLANT_TYPES = ["срезанный", "горшечный"]
POSITIONS = ["флорист", "курьер"]
COMPLEXITIES = ["простой", "средний", "сложный"]
PAYMENT_METHODS = ["наличные", "карта", "перевод"]
WRITEOFF_REASONS = ["увядание", "брак", "повреждение"]
REQUEST_STATUSES = ["новая", "выполнена", "отменена"]


def fmt(value):
    """Значение из БД в текст для таблицы."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def new_table():
    """Таблица только для чтения: выделяется строка целиком."""
    table = QTableWidget()
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectRows)
    table.setSelectionMode(QAbstractItemView.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def fill_table(table, columns, rows, hidden=1):
    """Заполняет таблицу. Первые hidden колонок (id) скрыты.

    Исходное значение каждой ячейки хранится в Qt.UserRole.
    """
    table.clear()
    table.setColumnCount(len(columns))
    table.setRowCount(len(rows))
    table.setHorizontalHeaderLabels(columns)
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(fmt(value))
            item.setData(Qt.UserRole, value)
            table.setItem(r, c, item)
    for c in range(len(columns)):
        table.setColumnHidden(c, c < hidden)
    table.resizeColumnsToContents()


def selected_value(table, column):
    """Значение колонки column в выделенной строке или None."""
    row = table.currentRow()
    if row < 0 or not table.selectionModel().hasSelection():
        return None
    return table.item(row, column).data(Qt.UserRole)


def selected_id(table):
    """id выделенной строки (скрытая колонка 0) или None."""
    return selected_value(table, 0)


def show_error(parent, e):
    QMessageBox.warning(parent, "Ошибка", db.error_text(e))


def message(parent, text):
    QMessageBox.information(parent, "Флористический центр", text)


def confirm(parent, text):
    answer = QMessageBox.question(parent, "Подтверждение", text,
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return answer == QMessageBox.Yes
