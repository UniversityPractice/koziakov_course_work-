"""Запуск приложения «Флористический центр»: подключение к БД и главное окно."""
import sys

import psycopg2
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox, QTabWidget, QWidget

import db


class StubTab(QWidget):
    """Временная заглушка вкладки (заменяется экранами по мере разработки)."""

    def refresh(self):
        pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Флористический центр")
        self.resize(1100, 700)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        for title, tab in self.build_tabs():
            self.tabs.addTab(tab, title)
        # при переходе на вкладку её данные перечитываются из БД
        self.tabs.currentChanged.connect(lambda index: self.tabs.widget(index).refresh())
        self.tabs.currentWidget().refresh()

    def build_tabs(self):
        titles = ["Растения", "Категории", "Поставщики", "Сотрудники", "Клиенты",
                  "Книга рецептов", "Заказы", "Списания", "Заявки на закупку", "Отчёты"]
        return [(title, StubTab()) for title in titles]


def main():
    app = QApplication(sys.argv)
    try:
        db.connect()
    except psycopg2.Error as e:
        p = db.read_config()
        QMessageBox.critical(None, "Нет подключения к БД",
                             f"Не удалось подключиться к БД {p['host']}:{p['port']}/{p['dbname']}\n\n"
                             f"{db.error_text(e)}\n\nПроверьте параметры в app/config.ini.")
        return 1
    window = MainWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
