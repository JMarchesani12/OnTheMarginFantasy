-- MOD-006: one linked profile per non-null auth subject.
-- Preserves nullable legacy UUIDs, email uniqueness and auth.users FK.
-- Never merges/deletes/links rows. Hosted aggregate preflight and approval are
-- prerequisites. Run as one transaction; bounded locks fail closed on busy DBs.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL row_security = off;
SET LOCAL statement_timeout = '60s';
LOCK TABLE public."User" IN SHARE ROW EXCLUSIVE MODE;
DO $migration$
DECLARE
    identity_column smallint;
    existing record;
BEGIN
    IF EXISTS (
        SELECT 1 FROM public."User" WHERE uuid IS NOT NULL
        GROUP BY uuid HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'MOD-006 blocked: duplicate linked profiles require reviewed remediation';
    END IF;

    SELECT attnum INTO STRICT identity_column
    FROM pg_attribute
    WHERE attrelid = 'public."User"'::regclass AND attname = 'uuid'
      AND NOT attisdropped;

    SELECT c.contype, c.conkey, c.condeferrable, c.convalidated,
           i.indnullsnotdistinct, i.indisvalid, i.indisready INTO existing
    FROM pg_constraint c
    LEFT JOIN pg_index i ON i.indexrelid = c.conindid
    WHERE c.conrelid = 'public."User"'::regclass AND c.conname = 'User_uuid_key';
    IF FOUND THEN
        IF existing.contype <> 'u' OR existing.conkey <> ARRAY[identity_column]
           OR existing.condeferrable OR NOT existing.convalidated
           OR existing.indnullsnotdistinct IS DISTINCT FROM false
           OR existing.indisvalid IS DISTINCT FROM true
           OR existing.indisready IS DISTINCT FROM true THEN
            RAISE EXCEPTION 'MOD-006 blocked: User_uuid_key has an unexpected definition';
        END IF;
    ELSE
        ALTER TABLE public."User" ADD CONSTRAINT "User_uuid_key" UNIQUE (uuid);
    END IF;
END
$migration$;
COMMIT;
