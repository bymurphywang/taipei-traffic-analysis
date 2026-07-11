-- 當事人年齡分組統計（佔比以全部當事人為分母，缺失年齡不列組）
WITH bucketed AS (
    SELECT
        CASE
            WHEN age < 18 THEN '未滿18歲'
            WHEN age <= 30 THEN '18-30歲'
            WHEN age <= 45 THEN '31-45歲'
            WHEN age <= 60 THEN '46-60歲'
            ELSE '60歲以上'
        END AS 年齡組,
        CASE
            WHEN age < 18 THEN 1
            WHEN age <= 30 THEN 2
            WHEN age <= 45 THEN 3
            WHEN age <= 60 THEN 4
            ELSE 5
        END AS sort_key
    FROM parties
    WHERE age IS NOT NULL
)
SELECT
    年齡組,
    COUNT(*)                                                       AS 人數,
    ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM parties), 2)    AS "佔比(%)"
FROM bucketed
GROUP BY 年齡組, sort_key
ORDER BY sort_key;
