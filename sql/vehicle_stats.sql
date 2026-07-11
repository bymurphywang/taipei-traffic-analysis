-- 各車種涉入統計（以當事人人次計，佔比以有車種代碼者為分母）
SELECT
    p.vehicle_code                                       AS 車種代碼,
    v.label                                              AS 車種名稱,
    COUNT(*)                                             AS 涉入件數,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)   AS "佔比(%)"
FROM parties p
LEFT JOIN vehicle_codes v ON v.code = p.vehicle_code
WHERE p.vehicle_code IS NOT NULL
GROUP BY p.vehicle_code, v.label
ORDER BY 涉入件數 DESC;
