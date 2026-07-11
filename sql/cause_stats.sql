-- 主要肇因統計（前 15 名）
-- 僅統計第一當事人（accidents.cause_code），與官方報告口徑一致
WITH by_cause AS (
    SELECT
        cause_code AS 肇因碼,
        COUNT(*)   AS 事故件數
    FROM accidents
    WHERE cause_code IS NOT NULL
    GROUP BY cause_code
)
SELECT
    b.肇因碼,
    c.label AS 肇因描述,
    b.事故件數,
    ROUND(100.0 * b.事故件數 / (SELECT COUNT(*) FROM accidents), 2) AS "佔比(%)",
    ROUND(100.0 * SUM(b.事故件數) OVER (
        ORDER BY b.事故件數 DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / (SELECT COUNT(*) FROM accidents), 2)                        AS "累積佔比(%)"
FROM by_cause b
LEFT JOIN cause_codes c ON c.code = b.肇因碼
ORDER BY b.事故件數 DESC
LIMIT 15;
