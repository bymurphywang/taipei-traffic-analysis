-- 24 小時事故分布（以事故件數統計）
SELECT
    hour                                                 AS 發生時,
    COUNT(*)                                             AS 事故件數,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)   AS "佔比(%)"
FROM accidents
GROUP BY hour
ORDER BY hour;
