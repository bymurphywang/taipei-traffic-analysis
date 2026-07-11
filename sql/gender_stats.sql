-- 當事人性別分布（佔比以全部當事人為分母）
SELECT
    gender_code                                                    AS 性別代碼,
    COUNT(*)                                                       AS 人數,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM parties), 2)    AS "佔比(%)"
FROM parties
WHERE gender_code IS NOT NULL
GROUP BY gender_code
ORDER BY 人數 DESC;
