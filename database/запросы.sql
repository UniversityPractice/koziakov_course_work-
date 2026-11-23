-- Семь запросов задания (листинги 3.7–3.13 пояснительной записки).
-- В приложении те же тексты лежат в app/sql.py; в запросах 2 и 3 даты заданы параметрами.

-- Запрос 1
SELECT р.название,
       SUM(сб.количество) AS использовано_шт
FROM состав_букета сб
JOIN букеты   б ON б.id = сб.букет_id
JOIN заказы   з ON з.id = б.заказ_id
JOIN растения р ON р.id = сб.растение_id
WHERE з.дата >= date_trunc('quarter', now()) - interval '3 months'
  AND з.дата <  date_trunc('quarter', now())
GROUP BY р.id, р.название
ORDER BY использовано_шт DESC, р.название
LIMIT 10;

-- Запрос 2
SELECT б.id                                             AS букет,
       з.дата::date                                     AS дата,
       COALESCE(ш.название, 'индивидуальный')           AS шаблон,
       SUM(сб.количество * сб.закупочная_цена)          AS себестоимость,
       б.цена_продажи,
       б.цена_продажи - SUM(сб.количество * сб.закупочная_цена) AS наценка
FROM букеты б
JOIN заказы з         ON з.id = б.заказ_id
JOIN состав_букета сб ON сб.букет_id = б.id
LEFT JOIN шаблоны ш   ON ш.id = б.шаблон_id
GROUP BY б.id, з.дата, ш.название
ORDER BY з.дата DESC, б.id;

-- Запрос 3
SELECT с.фио,
       COUNT(з.id) AS заказов,
       COALESCE(SUM(в.букеты + в.растения), 0) AS выручка
FROM сотрудники с
LEFT JOIN заказы з ON з.флорист_id = с.id
                  AND з.дата >= DATE '2026-01-01' AND з.дата < DATE '2026-10-01'
LEFT JOIN LATERAL (
       SELECT COALESCE((SELECT SUM(цена_продажи) FROM букеты
                        WHERE заказ_id = з.id), 0) AS букеты,
              COALESCE((SELECT SUM(количество * цена) FROM растения_в_заказе
                        WHERE заказ_id = з.id), 0) AS растения
) в ON TRUE
WHERE с.должность = 'флорист'
GROUP BY с.id, с.фио
ORDER BY выручка DESC;

-- Запрос 4
SELECT р.название, р.остаток, р.мин_остаток,
       п.название AS поставщик, п.телефон
FROM растения р
JOIN поставщики п ON п.id = р.поставщик_id
WHERE р.остаток < р.мин_остаток
ORDER BY р.остаток::numeric / NULLIF(р.мин_остаток, 0);

-- Запрос 5
SELECT to_char(м.месяц, 'MM') AS месяц,
       COUNT(з.id)          AS заказов
FROM generate_series(date_trunc('year', now()) - interval '1 year',
                     date_trunc('year', now()) - interval '1 month',
                     interval '1 month') AS м(месяц)
LEFT JOIN заказы з ON date_trunc('month', з.дата) = м.месяц
GROUP BY м.месяц
ORDER BY м.месяц;

-- Запрос 6
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
           ORDER BY к.название)) AS прайс
FROM категории к;

-- Запрос 7
SELECT б.сложность,
       COUNT(*)                        AS букетов,
       ROUND(AVG(б.время_сборки), 1)   AS среднее_мин
FROM букеты б
GROUP BY б.сложность
ORDER BY CASE б.сложность WHEN 'простой' THEN 1 WHEN 'средний' THEN 2 ELSE 3 END;
