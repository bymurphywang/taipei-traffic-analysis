-- 四時段事故分布（以事故件數統計）
SELECT
    time_period                                          AS 時段,
    COUNT(*)                                             AS 事故件數,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)   AS "佔比(%)"
FROM accidents
GROUP BY time_period
ORDER BY 事故件數 DESC;
