-- 各月份事故件數與傷亡統計
-- 死亡人數以 24 小時內死亡計，與官方報告口徑一致
SELECT
    month                                                          AS 發生月,
    COUNT(*)                                                       AS 事故件數,
    SUM(deaths_24h)                                                AS 死亡人數,
    SUM(injuries)                                                  AS 受傷人數,
    SUM(deaths_24h) + SUM(injuries)                                AS 傷亡總計,
    ROUND(1.0 * (SUM(deaths_24h) + SUM(injuries)) / COUNT(*), 2)   AS "平均傷亡/件"
FROM accidents
GROUP BY month
ORDER BY month;
