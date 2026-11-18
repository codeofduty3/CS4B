DROP VIEW IF EXISTS holdings_v;

CREATE VIEW holdings_v AS
SELECT
    h.adsh,
    f.name AS bdc,
    f.form,
    f.period,
    h.identifier,
    h.investment_type,
    h.industry,
    h.fair_value,
    h.cost,
    -- a holding with no fair value cannot be priced: treat it as non-debt
    CASE WHEN h.fair_value IS NOT NULL THEN h.principal END AS principal,
    CASE WHEN h.principal > 0 AND h.fair_value IS NOT NULL
         THEN 100.0 * h.fair_value / h.principal
         ELSE NULL
    END AS price,
    h.pik_rate,
    h.interest_rate,
    h.spread,
    h.maturity,
    CASE WHEN h.principal > 0 AND h.fair_value IS NOT NULL
         THEN 1 ELSE 0
    END AS is_debt
FROM holdings AS h
JOIN filings AS f ON f.adsh = h.adsh
WHERE h.period_role = 'current';
