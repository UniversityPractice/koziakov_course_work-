"""Работа с базой данных.

Одно соединение на всё приложение. Чтение — fetch / fetch_value,
запись — execute (одна команда) или transaction (несколько команд
одной транзакцией). error_text превращает ошибку PostgreSQL в понятный текст.
"""
import configparser
import re
from contextlib import contextmanager
from pathlib import Path

import psycopg2

CONFIG_PATH = Path(__file__).with_name("config.ini")

conn = None  # соединение, открывается в connect()


def read_config(path=CONFIG_PATH):
    """Параметры подключения из секции [database] файла config.ini."""
    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")
    return dict(parser["database"])


def connect(params=None):
    """Открывает соединение. Без параметров берёт их из config.ini."""
    global conn
    conn = psycopg2.connect(**(params or read_config()), client_encoding="UTF8")


def fetch(sql_text, params=None):
    """Выполняет SELECT и возвращает (названия колонок, список строк)."""
    try:
        with conn.cursor() as cur:
            cur.execute(sql_text, params)
            columns = [column.name for column in cur.description]
            return columns, cur.fetchall()
    finally:
        conn.rollback()  # не держим открытую транзакцию после чтения


def fetch_value(sql_text, params=None):
    """Первое значение первой строки результата или None."""
    rows = fetch(sql_text, params)[1]
    return rows[0][0] if rows else None


def execute(sql_text, params=None):
    """Выполняет одну команду записи в транзакции.

    Если команда что-то возвращает (RETURNING id), возвращает первое значение.
    При ошибке транзакция откатывается, исключение передаётся дальше.
    """
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql_text, params)
            if cur.description is not None:
                row = cur.fetchone()
                return row[0] if row else None
    return None


@contextmanager
def transaction():
    """Курсор для нескольких команд одной транзакцией.

    Выход из блока — COMMIT, исключение внутри блока — ROLLBACK.
    """
    with conn:
        with conn.cursor() as cur:
            yield cur


def error_text(e):
    """Понятное сообщение об ошибке БД (по коду ошибки PostgreSQL)."""
    code = getattr(e, "pgcode", None)
    diag = getattr(e, "diag", None)

    if code == "23503":  # нарушение внешнего ключа
        return f"Запись используется в таблице «{diag.table_name}», удалить её нельзя."
    if code == "23505":  # нарушение уникальности
        found = re.search(r"\((.*?)\)=\((.*?)\)", diag.message_detail or "")
        if found:
            column = found.group(1).replace('"', "")
            return f"Такое значение уже есть: {column} = {found.group(2)}."
        return "Такое значение уже есть."
    if code == "23514":  # нарушение CHECK
        return f"Недопустимое значение (условие {diag.constraint_name})."
    if code == "23502":  # NOT NULL
        return f"Не заполнено поле «{diag.column_name}»."
    if code == "P0001":  # RAISE EXCEPTION из триггера — текст уже по-русски
        return diag.message_primary
    if diag is not None and diag.message_primary:
        return diag.message_primary
    return str(e).strip()
