-- 肇因 × 車種交叉分析
-- 步驟：
--   1. 取事故件數前 5 大肇因（第一當事人口徑）
--   2. 統計「個別肇因」為該代碼的所有當事人之車種分布
--   3. 每個肇因取涉入人次前 5 名車種
-- 佔比分母為該肇因的全部當事人（含無車種代碼者，如行人以外的特殊記錄）
WITH top_causes AS (
    SELECT
        cause_code,
        COUNT(*) AS n_accidents
    FROM accidents
    WHERE cause_code IS NOT NULL
    GROUP BY cause_code
    ORDER BY n_accidents DESC
    LIMIT 5
),
totals AS (
    SELECT
        p.cause_code_individual AS cause_code,
        COUNT(*)                AS total_parties
    FROM parties p
    JOIN top_causes t ON t.cause_code = p.cause_code_individual
    GROUP BY p.cause_code_individual
),
ranked AS (
    SELECT
        p.cause_code_individual AS cause_code,
        p.vehicle_code,
        COUNT(*)                AS n_parties,
        ROW_NUMBER() OVER (
            PARTITION BY p.cause_code_individual
            ORDER BY COUNT(*) DESC
        )                       AS rk
    FROM parties p
    JOIN top_causes t ON t.cause_code = p.cause_code_individual
    WHERE p.vehicle_code IS NOT NULL
    GROUP BY p.cause_code_individual, p.vehicle_code
)
SELECT
    r.cause_code                                        AS 肇因碼,
    cc.label                                            AS 肇因描述,
    r.rk                                                AS 排名,
    r.vehicle_code                                      AS 車種代碼,
    vc.label                                            AS 車種名稱,
    r.n_parties                                         AS 涉入人次,
    ROUND(100.0 * r.n_parties / tt.total_parties, 2)    AS "佔該肇因比例(%)"
FROM ranked r
JOIN top_causes t  ON t.cause_code = r.cause_code
JOIN totals tt     ON tt.cause_code = r.cause_code
LEFT JOIN cause_codes cc   ON cc.code = r.cause_code
LEFT JOIN vehicle_codes vc ON vc.code = r.vehicle_code
WHERE r.rk <= 5
ORDER BY t.n_accidents DESC, r.rk;
