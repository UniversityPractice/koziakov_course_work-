"""Общие фикстуры тестов.

Перед тестами создаётся отдельная база florist_test из скриптов database/,
чтобы тесты не трогали рабочую базу florist.
"""
import configparser
import os
import re
import sys
from pathlib import Path

import psycopg2
import pytest

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
DATABASE = ROOT / "database"
sys.path.insert(0, str(APP))

_config = configparser.ConfigParser()
_config.read(APP / "config.ini", encoding="utf-8")
TEST_PARAMS = dict(_config["database"])
TEST_PARAMS["dbname"] = "florist_test"

# Защита рабочей базы: даже если код приложения прочитает config.ini сам
# (db.read_config), в тестах он получит тестовую базу.
os.environ["DB_DBNAME"] = "florist_test"


@pytest.fixture(scope="session", autouse=True)
def never_touch_work_db():
    """После всех тестов соединение приложения должно смотреть в тестовую базу."""
    yield
    import db
    assert db._params is None or db._params["dbname"] == "florist_test", db._params


def read_script(name):
    return (DATABASE / name).read_text(encoding="utf-8")


def query_blocks():
    """Делит запросы.sql на {номер: текст} по строкам «-- Запрос N»."""
    parts = re.split(r"^-- Запрос (\d+)\s*$", read_script("запросы.sql"), flags=re.M)
    return {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts), 2)}


@pytest.fixture(scope="session", autouse=True)
def test_db():
    admin = psycopg2.connect(**{**TEST_PARAMS, "dbname": "postgres"})
    admin.autocommit = True
    with admin.cursor() as c:
        c.execute("DROP DATABASE IF EXISTS florist_test WITH (FORCE)")
        c.execute("CREATE DATABASE florist_test ENCODING 'UTF8' TEMPLATE template0")
    admin.close()

    conn = psycopg2.connect(**TEST_PARAMS)
    conn.autocommit = True
    with conn.cursor() as c:
        c.execute(read_script("флористический_центр.sql"))
        c.execute(read_script("тестовые_данные.sql"))
    conn.close()
    yield


@pytest.fixture
def cur(test_db):
    conn = psycopg2.connect(**TEST_PARAMS)
    conn.autocommit = True
    with conn.cursor() as c:
        yield c
    conn.close()


@pytest.fixture(scope="session", autouse=True)
def db_connection(test_db):
    """Модуль db приложения подключён к тестовой базе."""
    import db
    db.connect(TEST_PARAMS)
    yield
    db.conn.close()


@pytest.fixture
def client():
    """Тестовый клиент сайта (страницы запрашиваются без запуска сервера)."""
    from main import app
    app.config["TESTING"] = True
    return app.test_client()
