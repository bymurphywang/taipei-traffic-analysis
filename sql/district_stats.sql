-- 各行政區事故統計，含佔比與累積佔比（窗函數）
WITH by_district AS (
    SELECT
        district        AS 行政區,
        COUNT(*)        AS 事故件數,
        SUM(deaths_24h) AS 死亡人數,
        SUM(injuries)   AS 受傷人數
    FROM accidents
    GROUP BY district
)
SELECT
    行政區,
    事故件數,
    死亡人數,
    受傷人數,
    ROUND(100.0 * 事故件數 / SUM(事故件數) OVER (), 2) AS "佔比(%)",
    ROUND(100.0 * SUM(事故件數) OVER (
        ORDER BY 事故件數 DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) / SUM(事故件數) OVER (), 2)                       AS "累積佔比(%)"
FROM by_district
ORDER BY 事故件數 DESC;
