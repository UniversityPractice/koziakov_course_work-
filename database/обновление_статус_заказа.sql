-- =====================================================================
-- Обновление уже созданной базы: статус заказа и время вручения.
-- Новой базе не нужен — всё это уже есть в флористический_центр.sql.
-- Запуск (данные сохраняются):
--   docker cp database florist-db:/database
--   docker exec florist-db psql -U postgres -d florist -f /database/обновление_статус_заказа.sql
-- =====================================================================
BEGIN;

ALTER TABLE заказы
    ADD COLUMN статус VARCHAR(12) NOT NULL DEFAULT 'принят'
        CHECK (статус IN ('принят', 'в доставке', 'вручён', 'не вручён')),
    ADD COLUMN время_вручения TIMESTAMP;

-- Прошедшие заказы считаем вручёнными в назначенное время,
-- остальные с курьером — в доставке.
UPDATE заказы
   SET статус = 'вручён', время_вручения = COALESCE(время_доставки, дата)
 WHERE COALESCE(время_доставки, дата) < now();
UPDATE заказы SET статус = 'в доставке'
 WHERE статус = 'принят' AND курьер_id IS NOT NULL;

ALTER TABLE заказы
    ADD CONSTRAINT вручён_со_временем CHECK ((статус = 'вручён') = (время_вручения IS NOT NULL));

-- Триггер — тот же, что в конце флористический_центр.sql.
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

COMMIT;
