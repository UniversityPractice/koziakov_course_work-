-- =====================================================================
-- База данных «Флористический центр»
-- Курсовая работа по дисциплине «Проектирование баз данных»
-- Листинги 3.1–3.6 пояснительной записки + статус заказа (в конце файла).
-- Расписание pg_cron вынесено в pg_cron.sql (расширение есть не везде).
-- =====================================================================

-- ---------------------------------------------------------------------
-- 3.1. Последовательности и таблицы
-- ---------------------------------------------------------------------
CREATE SEQUENCE посл_категории;
CREATE SEQUENCE посл_поставщики;
CREATE SEQUENCE посл_растения;
CREATE SEQUENCE посл_сотрудники;
CREATE SEQUENCE посл_шаблоны;
CREATE SEQUENCE посл_клиенты;
CREATE SEQUENCE посл_заказы;
CREATE SEQUENCE посл_букеты;
CREATE SEQUENCE посл_списания;
CREATE SEQUENCE посл_заявки;

CREATE TABLE категории (
    id            INT PRIMARY KEY DEFAULT nextval('посл_категории'),
    название      VARCHAR(100) NOT NULL UNIQUE,
    коэф_наценки  NUMERIC(4,2) NOT NULL CHECK (коэф_наценки >= 1)
);

CREATE TABLE поставщики (
    id             INT PRIMARY KEY DEFAULT nextval('посл_поставщики'),
    название       VARCHAR(150) NOT NULL,
    телефон        VARCHAR(20),
    срок_поставки  INT NOT NULL DEFAULT 1 CHECK (срок_поставки > 0)   -- дни
);

CREATE TABLE растения (
    id               INT PRIMARY KEY DEFAULT nextval('посл_растения'),
    название         VARCHAR(150)  NOT NULL UNIQUE,
    тип              VARCHAR(20)   NOT NULL CHECK (тип IN ('срезанный', 'горшечный')),
    категория_id     INT           NOT NULL REFERENCES категории(id),
    поставщик_id     INT           NOT NULL REFERENCES поставщики(id),
    закупочная_цена  NUMERIC(10,2) NOT NULL CHECK (закупочная_цена >= 0),
    остаток          INT           NOT NULL DEFAULT 0 CHECK (остаток >= 0),
    мин_остаток      INT           NOT NULL DEFAULT 0 CHECK (мин_остаток >= 0)
);

CREATE TABLE сотрудники (
    id         INT PRIMARY KEY DEFAULT nextval('посл_сотрудники'),
    фио        VARCHAR(150) NOT NULL,
    должность  VARCHAR(20)  NOT NULL CHECK (должность IN ('флорист', 'курьер')),
    телефон    VARCHAR(20)
);

CREATE TABLE шаблоны (
    id          INT PRIMARY KEY DEFAULT nextval('посл_шаблоны'),
    флорист_id  INT          NOT NULL REFERENCES сотрудники(id),
    название    VARCHAR(150) NOT NULL
);

CREATE TABLE состав_шаблона (
    шаблон_id    INT NOT NULL REFERENCES шаблоны(id) ON DELETE CASCADE,
    растение_id  INT NOT NULL REFERENCES растения(id),
    количество   INT NOT NULL CHECK (количество > 0),
    PRIMARY KEY (шаблон_id, растение_id)
);

CREATE TABLE клиенты (
    id       INT PRIMARY KEY DEFAULT nextval('посл_клиенты'),
    имя      VARCHAR(100) NOT NULL,
    телефон  VARCHAR(20)  UNIQUE,          -- NULL, если клиент не назвал
    email    VARCHAR(100)
);

CREATE TABLE заказы (
    id                  INT PRIMARY KEY DEFAULT nextval('посл_заказы'),
    дата                TIMESTAMP   NOT NULL DEFAULT now(),
    клиент_id           INT         NOT NULL REFERENCES клиенты(id),
    флорист_id          INT         NOT NULL REFERENCES сотрудники(id),
    способ_оплаты       VARCHAR(10) NOT NULL
                        CHECK (способ_оплаты IN ('наличные', 'карта', 'перевод')),
    курьер_id           INT         REFERENCES сотрудники(id),  -- NULL = самовывоз
    адрес_доставки      VARCHAR(255),
    время_доставки      TIMESTAMP,
    получатель          VARCHAR(100),   -- NULL = получает сам клиент
    телефон_получателя  VARCHAR(20),
    -- доставка: принят → в доставке → вручён (или «не вручён» и повторная доставка);
    -- самовывоз: принят → вручён. Переходы проверяет триггер тр_статус_заказа.
    статус              VARCHAR(12) NOT NULL DEFAULT 'принят'
                        CHECK (статус IN ('принят', 'в доставке', 'вручён', 'не вручён')),
    время_вручения      TIMESTAMP,      -- когда заказчик принял заказ
    CONSTRAINT вручён_со_временем CHECK ((статус = 'вручён') = (время_вручения IS NOT NULL))
);

CREATE TABLE растения_в_заказе (
    заказ_id     INT           NOT NULL REFERENCES заказы(id) ON DELETE CASCADE,
    растение_id  INT           NOT NULL REFERENCES растения(id),
    количество   INT           NOT NULL CHECK (количество > 0),
    цена         NUMERIC(10,2) NOT NULL CHECK (цена >= 0),
    PRIMARY KEY (заказ_id, растение_id)
);

CREATE TABLE букеты (
    id            INT PRIMARY KEY DEFAULT nextval('посл_букеты'),
    заказ_id      INT           NOT NULL REFERENCES заказы(id) ON DELETE CASCADE,
    шаблон_id     INT           REFERENCES шаблоны(id) ON DELETE SET NULL,
    сложность     VARCHAR(10)   NOT NULL
                  CHECK (сложность IN ('простой', 'средний', 'сложный')),
    время_сборки  INT           NOT NULL CHECK (время_сборки > 0),          -- минуты
    цена_продажи  NUMERIC(10,2) NOT NULL CHECK (цена_продажи >= 0)
);

CREATE TABLE состав_букета (
    букет_id         INT           NOT NULL REFERENCES букеты(id) ON DELETE CASCADE,
    растение_id      INT           NOT NULL REFERENCES растения(id),
    количество       INT           NOT NULL CHECK (количество > 0),
    закупочная_цена  NUMERIC(10,2) NOT NULL CHECK (закупочная_цена >= 0),
    PRIMARY KEY (букет_id, растение_id)
);

CREATE TABLE списания (
    id           INT PRIMARY KEY DEFAULT nextval('посл_списания'),
    растение_id  INT         NOT NULL REFERENCES растения(id),
    дата         TIMESTAMP   NOT NULL DEFAULT now(),
    количество   INT         NOT NULL CHECK (количество > 0),
    причина      VARCHAR(20) NOT NULL
                 CHECK (причина IN ('увядание', 'брак', 'повреждение'))
);

CREATE TABLE заявки_на_закупку (
    id              INT PRIMARY KEY DEFAULT nextval('посл_заявки'),
    растение_id     INT         NOT NULL REFERENCES растения(id),
    количество      INT         NOT NULL CHECK (количество > 0),
    дата            TIMESTAMP   NOT NULL DEFAULT now(),
    ожидаемая_дата  DATE        NOT NULL,
    статус          VARCHAR(10) NOT NULL DEFAULT 'новая'
                    CHECK (статус IN ('новая', 'выполнена', 'отменена'))
);

ALTER SEQUENCE посл_категории  OWNED BY категории.id;
ALTER SEQUENCE посл_поставщики OWNED BY поставщики.id;
ALTER SEQUENCE посл_растения   OWNED BY растения.id;
ALTER SEQUENCE посл_сотрудники OWNED BY сотрудники.id;
ALTER SEQUENCE посл_шаблоны    OWNED BY шаблоны.id;
ALTER SEQUENCE посл_клиенты    OWNED BY клиенты.id;
ALTER SEQUENCE посл_заказы     OWNED BY заказы.id;
ALTER SEQUENCE посл_букеты     OWNED BY букеты.id;
ALTER SEQUENCE посл_списания   OWNED BY списания.id;
ALTER SEQUENCE посл_заявки     OWNED BY заявки_на_закупку.id;

-- ---------------------------------------------------------------------
-- 3.2. Функция расчёта рекомендуемой цены букета
-- ---------------------------------------------------------------------
CREATE FUNCTION рекоменд_цена(p_букет_id INT) RETURNS NUMERIC AS $$
    SELECT COALESCE(ROUND(SUM(сб.количество * р.закупочная_цена * к.коэф_наценки), 2), 0)
    FROM состав_букета сб
    JOIN растения  р ON р.id = сб.растение_id
    JOIN категории к ON к.id = р.категория_id
    WHERE сб.букет_id = p_букет_id;
$$ LANGUAGE sql STABLE;

-- ---------------------------------------------------------------------
-- 3.4. Функция проверить_запас (вызывается из тр_склад, поэтому создаётся раньше)
-- ---------------------------------------------------------------------
CREATE FUNCTION проверить_запас(p_растение_id INT) RETURNS VOID AS $$
DECLARE
    v_остаток   INT;
    v_мин       INT;
    v_срок      INT;
    v_расход    NUMERIC;
    v_в_пути    INT;
    v_точка     INT;
    v_заказать  INT;
BEGIN
    SELECT р.остаток, р.мин_остаток, п.срок_поставки
      INTO v_остаток, v_мин, v_срок
      FROM растения р JOIN поставщики п ON п.id = р.поставщик_id
     WHERE р.id = p_растение_id;

    -- средний расход в день за 30 дней: в букетах и отдельными растениями
    SELECT COALESCE(SUM(кол), 0) / 30.0 INTO v_расход
      FROM (SELECT сб.количество AS кол
              FROM состав_букета сб
              JOIN букеты б ON б.id = сб.букет_id
              JOIN заказы з ON з.id = б.заказ_id
             WHERE сб.растение_id = p_растение_id
               AND з.дата >= now() - interval '30 days'
            UNION ALL
            SELECT рз.количество
              FROM растения_в_заказе рз
              JOIN заказы з ON з.id = рз.заказ_id
             WHERE рз.растение_id = p_растение_id
               AND з.дата >= now() - interval '30 days') продажи;

    -- товар в пути: заказан, но ещё не привезён
    SELECT COALESCE(SUM(количество), 0) INTO v_в_пути
      FROM заявки_на_закупку
     WHERE растение_id = p_растение_id AND статус = 'новая';

    v_точка := CEIL(v_расход * v_срок) + v_мин;                    -- формула (3.3)

    IF v_остаток + v_в_пути < v_точка THEN
        v_заказать := CEIL(v_расход * (v_срок + 7)) + v_мин
                      - v_остаток - v_в_пути;                    -- формула (3.4)
        INSERT INTO заявки_на_закупку (растение_id, количество, ожидаемая_дата)
        VALUES (p_растение_id, v_заказать, CURRENT_DATE + v_срок);
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 3.3. Триггерная функция складского учёта
-- ---------------------------------------------------------------------
CREATE FUNCTION тр_склад() RETURNS TRIGGER AS $$
DECLARE
    v_остаток   INT;
    v_название  VARCHAR;
    v_закуп     NUMERIC;
    v_коэф      NUMERIC;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        UPDATE растения SET остаток = остаток + OLD.количество WHERE id = OLD.растение_id;
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        END IF;
    END IF;

    SELECT р.остаток, р.название, р.закупочная_цена, к.коэф_наценки
      INTO v_остаток, v_название, v_закуп, v_коэф
      FROM растения р JOIN категории к ON к.id = р.категория_id
     WHERE р.id = NEW.растение_id
       FOR UPDATE OF р;

    IF v_остаток < NEW.количество THEN
        RAISE EXCEPTION 'Недостаточно «%» на складе: есть %, нужно %',
                        v_название, v_остаток, NEW.количество;
    END IF;

    UPDATE растения SET остаток = остаток - NEW.количество WHERE id = NEW.растение_id;

    IF TG_TABLE_NAME = 'состав_букета' THEN
        IF NEW.закупочная_цена IS NULL THEN
            NEW.закупочная_цена := v_закуп;
        END IF;
    ELSIF TG_TABLE_NAME = 'растения_в_заказе' THEN
        IF NEW.цена IS NULL THEN
            NEW.цена := ROUND(v_закуп * v_коэф, 2);
        END IF;
    END IF;

    PERFORM проверить_запас(NEW.растение_id);

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER склад_состав_букета
    BEFORE INSERT OR UPDATE OR DELETE ON состав_букета
    FOR EACH ROW EXECUTE FUNCTION тр_склад();

CREATE TRIGGER склад_растения_в_заказе
    BEFORE INSERT OR UPDATE OR DELETE ON растения_в_заказе
    FOR EACH ROW EXECUTE FUNCTION тр_склад();

CREATE TRIGGER склад_списания
    BEFORE INSERT OR UPDATE OR DELETE ON списания
    FOR EACH ROW EXECUTE FUNCTION тр_склад();

-- ---------------------------------------------------------------------
-- 3.4. Процедура сформировать_заявки (запуск по расписанию — pg_cron.sql
--      или кнопкой «Сформировать заявки» в приложении)
-- ---------------------------------------------------------------------
CREATE PROCEDURE сформировать_заявки() AS $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT id FROM растения ORDER BY id LOOP
        PERFORM проверить_запас(r.id);
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- ---------------------------------------------------------------------
-- 3.4. Триггерная функция тр_поставка: выполненная заявка пополняет склад
-- ---------------------------------------------------------------------
CREATE FUNCTION тр_поставка() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.статус <> 'новая' THEN
        RAISE EXCEPTION 'Заявка % уже закрыта, изменять её нельзя', OLD.id;
    END IF;
    IF NEW.статус = 'выполнена' THEN
        UPDATE растения SET остаток = остаток + NEW.количество
         WHERE id = NEW.растение_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER поставка_заявки
    BEFORE UPDATE ON заявки_на_закупку
    FOR EACH ROW EXECUTE FUNCTION тр_поставка();

-- ---------------------------------------------------------------------
-- Статус заказа (дополнение к листингам 3.1–3.6).
-- Растения списываются со склада при оформлении заказа (тр_склад):
-- собранный букет продать другому клиенту уже нельзя. Статус отмечает,
-- что заказ вручён. Отменить (удалить) можно только заказ в статусе
-- «принят» — тогда растения возвращаются на склад. Вручённый заказ
-- не меняется; невручённый остаётся списанным, его можно доставить снова.
-- ---------------------------------------------------------------------
CREATE FUNCTION тр_статус_заказа() RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.статус <> 'принят' THEN
            RAISE EXCEPTION 'Заказ % уже в статусе «%», отменить его нельзя', OLD.id, OLD.статус;
        END IF;
        RETURN OLD;
    END IF;

    IF OLD.статус = 'вручён' THEN
        RAISE EXCEPTION 'Заказ % уже вручён, изменить его нельзя', OLD.id;
    END IF;
    IF NEW.статус <> OLD.статус THEN
        IF NEW.статус = 'принят' THEN
            RAISE EXCEPTION 'Вернуть заказ % в статус «принят» нельзя', OLD.id;
        END IF;
        IF NEW.статус = 'в доставке' AND NEW.курьер_id IS NULL THEN
            RAISE EXCEPTION 'Заказ % — самовывоз, курьер не назначен', OLD.id;
        END IF;
    END IF;

    IF NEW.статус = 'вручён' THEN
        NEW.время_вручения := COALESCE(NEW.время_вручения, now());
    ELSE
        NEW.время_вручения := NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER статус_заказа
    BEFORE UPDATE OR DELETE ON заказы
    FOR EACH ROW EXECUTE FUNCTION тр_статус_заказа();
