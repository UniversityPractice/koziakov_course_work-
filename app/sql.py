"""Все SQL-тексты приложения. В остальных модулях SQL нет.

Правила:
* только параметры %s — значения никогда не вставляются в текст запроса;
* INSERT не передаёт id: ключ выдаёт последовательность, а приложение
  получает его через RETURNING id;
* у запросов *_LIST первая колонка — id (на странице она не показывается).
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

# =====================================================================
# Заказы: растения списывает со склада тр_склад при оформлении,
# переходы статусов и запрет отмены проверяет тр_статус_заказа.
# Первые две колонки списка служебные: id и признак «с доставкой».
# =====================================================================
ORDER_LIST = """
    SELECT з.id, з.курьер_id IS NOT NULL AS "с доставкой",
           з.id AS "№", з.дата AS "Оформлен", кл.имя AS "Клиент", ф.фио AS "Флорист",
           COALESCE(з.адрес_доставки, 'самовывоз') AS "Адрес", з.время_доставки AS "К времени",
           кур.фио AS "Курьер",
           COALESCE((SELECT SUM(цена_продажи) FROM букеты WHERE заказ_id = з.id), 0)
         + COALESCE((SELECT SUM(количество * цена) FROM растения_в_заказе WHERE заказ_id = з.id), 0)
             AS "Сумма",
           з.статус AS "Статус", з.время_вручения AS "Вручён"
    FROM заказы з
    JOIN клиенты    кл ON кл.id = з.клиент_id
    JOIN сотрудники ф  ON ф.id  = з.флорист_id
    LEFT JOIN сотрудники кур ON кур.id = з.курьер_id
    WHERE CASE %(фильтр)s WHEN 'все'      THEN TRUE
                          WHEN 'активные' THEN з.статус <> 'вручён'
                          ELSE з.статус = %(фильтр)s END
    ORDER BY з.дата DESC, з.id DESC"""
ORDER_SET_STATUS = "UPDATE заказы SET статус = %s WHERE id = %s"
ORDER_DELETE = "DELETE FROM заказы WHERE id = %s"

# =====================================================================
# Заявки на закупку: создаёт их база (сформировать_заявки, тр_склад),
# склад при получении пополняет триггер тр_поставка.
# =====================================================================
REQUEST_LIST = """
    SELECT з.id, з.id AS "№", з.дата AS "Дата", р.название AS "Растение",
           п.название AS "Поставщик", п.срок_поставки AS "Срок, дн.",
           з.количество AS "Количество", з.ожидаемая_дата AS "Ожидается",
           з.статус AS "Статус"
    FROM заявки_на_закупку з
    JOIN растения   р ON р.id = з.растение_id
    JOIN поставщики п ON п.id = р.поставщик_id
    WHERE %(статус)s::varchar IS NULL OR з.статус = %(статус)s
    ORDER BY з.дата DESC, з.id DESC"""
REQUEST_COUNT = "SELECT COUNT(*) FROM заявки_на_закупку"
REQUEST_GENERATE = "CALL сформировать_заявки()"
REQUEST_SET_STATUS = "UPDATE заявки_на_закупку SET статус = %s WHERE id = %s"

# =====================================================================
# Отчёты — семь запросов задания (database/запросы.sql).
# Запрос 2: период необязателен (NULL — все букеты).
# Запрос 3: границы периода включительно.
# =====================================================================
REPORT_1 = """
    SELECT р.название AS "Растение", SUM(сб.количество) AS "Использовано, шт."
    FROM состав_букета сб
    JOIN букеты   б ON б.id = сб.букет_id
    JOIN заказы   з ON з.id = б.заказ_id
    JOIN растения р ON р.id = сб.растение_id
    WHERE з.дата >= date_trunc('quarter', now()) - interval '3 months'
      AND з.дата <  date_trunc('quarter', now())
    GROUP BY р.id, р.название
    ORDER BY 2 DESC, р.название
    LIMIT 10"""
REPORT_2 = """
    SELECT б.id AS "Букет", з.дата::date AS "Дата",
           COALESCE(ш.название, 'индивидуальный') AS "Шаблон",
           SUM(сб.количество * сб.закупочная_цена) AS "Себестоимость",
           б.цена_продажи AS "Цена продажи",
           б.цена_продажи - SUM(сб.количество * сб.закупочная_цена) AS "Наценка"
    FROM букеты б
    JOIN заказы з         ON з.id = б.заказ_id
    JOIN состав_букета сб ON сб.букет_id = б.id
    LEFT JOIN шаблоны ш   ON ш.id = б.шаблон_id
    WHERE (%(с)s::date IS NULL OR з.дата >= %(с)s::date)
      AND (%(по)s::date IS NULL OR з.дата < %(по)s::date + 1)
    GROUP BY б.id, з.дата, ш.название
    ORDER BY з.дата DESC, б.id"""
REPORT_3 = """
    SELECT с.фио AS "Флорист", COUNT(з.id) AS "Заказов",
           COALESCE(SUM(в.букеты + в.растения), 0) AS "Выручка"
    FROM сотрудники с
    LEFT JOIN заказы з ON з.флорист_id = с.id
                      AND з.дата >= %(с)s::date AND з.дата < %(по)s::date + 1
    LEFT JOIN LATERAL (
           SELECT COALESCE((SELECT SUM(цена_продажи) FROM букеты
                            WHERE заказ_id = з.id), 0) AS букеты,
                  COALESCE((SELECT SUM(количество * цена) FROM растения_в_заказе
                            WHERE заказ_id = з.id), 0) AS растения
    ) в ON TRUE
    WHERE с.должность = 'флорист'
    GROUP BY с.id, с.фио
    ORDER BY 3 DESC"""
REPORT_4 = """
    SELECT р.название AS "Растение", р.остаток AS "Остаток", р.мин_остаток AS "Мин. остаток",
           п.название AS "Поставщик", п.телефон AS "Телефон"
    FROM растения р
    JOIN поставщики п ON п.id = р.поставщик_id
    WHERE р.остаток < р.мин_остаток
    ORDER BY р.остаток::numeric / NULLIF(р.мин_остаток, 0)"""
REPORT_5 = """
    SELECT to_char(м.месяц, 'MM') AS "Месяц", COUNT(з.id) AS "Заказов"
    FROM generate_series(date_trunc('year', now()) - interval '1 year',
                         date_trunc('year', now()) - interval '1 month',
                         interval '1 month') AS м(месяц)
    LEFT JOIN заказы з ON date_trunc('month', з.дата) = м.месяц
    GROUP BY м.месяц
    ORDER BY м.месяц"""
REPORT_6 = """
    SELECT xmlelement(name "прайс_лист",
             xmlelement(name "дата", current_date),
             xmlagg(
               xmlelement(name "категория",
                 xmlelement(name "название", к.название),
                 (SELECT xmlagg(
                           xmlelement(name "растение",
                             xmlforest(р.название AS "название",
                                       р.тип      AS "тип",
                                       ROUND(р.закупочная_цена * к.коэф_наценки, 2) AS "цена"))
                           ORDER BY р.название)
                    FROM растения р WHERE р.категория_id = к.id))
               ORDER BY к.название))::text AS "Прайс-лист"
    FROM категории к"""
REPORT_7 = """
    SELECT б.сложность AS "Сложность", COUNT(*) AS "Букетов",
           ROUND(AVG(б.время_сборки), 1) AS "Среднее время, мин."
    FROM букеты б
    GROUP BY б.сложность
    ORDER BY CASE б.сложность WHEN 'простой' THEN 1 WHEN 'средний' THEN 2 ELSE 3 END"""
