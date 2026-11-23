"""Главное окно создаётся, все вкладки обновляются без ошибок."""
from main import MainWindow

TITLES = ["Растения", "Категории", "Поставщики", "Сотрудники", "Клиенты",
          "Книга рецептов", "Заказы", "Списания", "Заявки на закупку", "Отчёты"]


def test_main_window_tabs(qapp):
    window = MainWindow()
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == TITLES
    for i in range(window.tabs.count()):
        window.tabs.setCurrentIndex(i)
        window.tabs.widget(i).refresh()
