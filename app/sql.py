"""Все SQL-тексты приложения. В остальных модулях SQL нет.

Правила:
* только параметры %s — значения никогда не вставляются в текст запроса;
* INSERT не передаёт id: ключ выдаёт последовательность, а приложение
  получает его через RETURNING id;
* у запросов *_LIST первая колонка — id (в таблице на экране она скрыта).
"""

# =====================================================================
# Справочники: LIST — таблица на экране, GET — поля формы по id,
# INSERT/UPDATE — те же поля в том же порядке, DELETE — по id.
# =====================================================================

# --- Категории -------------------------------------------------------
CATEGORY_LIST = """
    SELECT id, название AS "Название", коэф_наценки AS "Коэф. наценки"
    FROM категории
    ORDER BY название"""
CATEGORY_GET = "SELECT название, коэф_наценки FROM категории WHERE id = %s"
CATEGORY_INSERT = "INSERT INTO категории (название, коэф_наценки) VALUES (%s, %s) RETURNING id"
CATEGORY_UPDATE = "UPDATE категории SET название = %s, коэф_наценки = %s WHERE id = %s"
CATEGORY_DELETE = "DELETE FROM категории WHERE id = %s"

# --- Поставщики ------------------------------------------------------
SUPPLIER_LIST = """
    SELECT id, название AS "Название", телефон AS "Телефон",
           срок_поставки AS "Срок поставки, дн."
    FROM поставщики
    ORDER BY название"""
SUPPLIER_GET = "SELECT название, телефон, срок_поставки FROM поставщики WHERE id = %s"
SUPPLIER_INSERT = """
    INSERT INTO поставщики (название, телефон, срок_поставки)
    VALUES (%s, %s, %s) RETURNING id"""
SUPPLIER_UPDATE = """
    UPDATE поставщики SET название = %s, телефон = %s, срок_поставки = %s
    WHERE id = %s"""
SUPPLIER_DELETE = "DELETE FROM поставщики WHERE id = %s"

# --- Растения (последняя скрытая колонка — признак «ниже минимума») ---
PLANT_LIST = """
    SELECT р.id, р.название AS "Название", р.тип AS "Тип",
           к.название AS "Категория", п.название AS "Поставщик",
           р.закупочная_цена AS "Закуп. цена",
           ROUND(р.закупочная_цена * к.коэф_наценки, 2) AS "Розн. цена",
           р.остаток AS "Остаток", р.мин_остаток AS "Мин. остаток",
           р.остаток < р.мин_остаток AS "мало"
    FROM растения р
    JOIN категории  к ON к.id = р.категория_id
    JOIN поставщики п ON п.id = р.поставщик_id
    ORDER BY р.название"""
PLANT_GET = """
    SELECT название, тип, категория_id, поставщик_id, закупочная_цена, остаток, мин_остаток
    FROM растения WHERE id = %s"""
PLANT_INSERT = """
    INSERT INTO растения (название, тип, категория_id, поставщик_id,
                          закупочная_цена, остаток, мин_остаток)
    VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"""
PLANT_UPDATE = """
    UPDATE растения
    SET название = %s, тип = %s, категория_id = %s, поставщик_id = %s,
        закупочная_цена = %s, остаток = %s, мин_остаток = %s
    WHERE id = %s"""
PLANT_DELETE = "DELETE FROM растения WHERE id = %s"

# --- Сотрудники ------------------------------------------------------
EMPLOYEE_LIST = """
    SELECT id, фио AS "ФИО", должность AS "Должность", телефон AS "Телефон"
    FROM сотрудники
    ORDER BY должность DESC, фио"""
EMPLOYEE_GET = "SELECT фио, должность, телефон FROM сотрудники WHERE id = %s"
EMPLOYEE_INSERT = "INSERT INTO сотрудники (фио, должность, телефон) VALUES (%s, %s, %s) RETURNING id"
EMPLOYEE_UPDATE = "UPDATE сотрудники SET фио = %s, должность = %s, телефон = %s WHERE id = %s"
EMPLOYEE_DELETE = "DELETE FROM сотрудники WHERE id = %s"

# --- Клиенты ---------------------------------------------------------
CLIENT_LIST = """
    SELECT id, имя AS "Имя", телефон AS "Телефон", email AS "Email"
    FROM клиенты
    ORDER BY имя"""
CLIENT_GET = "SELECT имя, телефон, email FROM клиенты WHERE id = %s"
CLIENT_INSERT = "INSERT INTO клиенты (имя, телефон, email) VALUES (%s, %s, %s) RETURNING id"
CLIENT_UPDATE = "UPDATE клиенты SET имя = %s, телефон = %s, email = %s WHERE id = %s"
CLIENT_DELETE = "DELETE FROM клиенты WHERE id = %s"

# --- Списания (остаток меняет триггер тр_склад) ------------------------
WRITEOFF_LIST = """
    SELECT с.id, с.дата AS "Дата", р.название AS "Растение",
           с.количество AS "Количество", с.причина AS "Причина"
    FROM списания с
    JOIN растения р ON р.id = с.растение_id
    ORDER BY с.дата DESC"""
WRITEOFF_GET = "SELECT растение_id, количество, причина FROM списания WHERE id = %s"
WRITEOFF_INSERT = """
    INSERT INTO списания (растение_id, количество, причина)
    VALUES (%s, %s, %s) RETURNING id"""
WRITEOFF_UPDATE = """
    UPDATE списания SET растение_id = %s, количество = %s, причина = %s
    WHERE id = %s"""
WRITEOFF_DELETE = "DELETE FROM списания WHERE id = %s"

# =====================================================================
# Выпадающие списки: (id, подпись)
# =====================================================================
CATEGORIES_LOOKUP = "SELECT id, название FROM категории ORDER BY название"
SUPPLIERS_LOOKUP = "SELECT id, название FROM поставщики ORDER BY название"
PLANTS_LOOKUP = """
    SELECT id, название || ' (ост. ' || остаток || ')'
    FROM растения ORDER BY название"""
FLORISTS_LOOKUP = "SELECT id, фио FROM сотрудники WHERE должность = 'флорист' ORDER BY фио"
COURIERS_LOOKUP = "SELECT id, фио FROM сотрудники WHERE должность = 'курьер' ORDER BY фио"
CLIENTS_LOOKUP = """
    SELECT id, имя || COALESCE(' — ' || телефон, '')
    FROM клиенты ORDER BY имя"""
