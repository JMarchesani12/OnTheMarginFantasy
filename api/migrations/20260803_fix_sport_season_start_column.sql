DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'SportSeason'
          AND column_name = 'esasonStart'
    ) AND NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'SportSeason'
          AND column_name = 'seasonStart'
    ) THEN
        ALTER TABLE public."SportSeason"
            RENAME COLUMN "esasonStart" TO "seasonStart";
    END IF;
END $$;
