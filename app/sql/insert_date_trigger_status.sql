INSERT INTO nifty.trigger_status (date, pct_trigger, atr, range)
SELECT CURRENT_DATE, NULL, NULL, NULL
WHERE NOT EXISTS (
    SELECT 1 FROM nifty.trigger_status WHERE date = CURRENT_DATE
);