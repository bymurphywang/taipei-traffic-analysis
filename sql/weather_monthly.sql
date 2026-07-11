-- 各月份雨天事故統計（天候代碼 6 = 雨）
SELECT
    month                                                          AS 發生月,
    COUNT(*)                                                       AS 事故件數,
    SUM(is_rain)                                                   AS 雨天事故件數,
    ROUND(100.0 * SUM(is_rain) / COUNT(*), 2)                      AS "雨天佔比(%)"
FROM accidents
GROUP BY month
ORDER BY month;
