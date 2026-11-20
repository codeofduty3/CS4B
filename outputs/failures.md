# Failure log

## Failure 1
Question:
How are current holdings and fair value divided between debt and equity?

What went wrong: The first SQL grouped by a `holding_class` column that does not exist in `holdings_v`; the execute trace returned `invalid: no such column: holding_class`.

What fixed it: The repair used the view's `is_debt` flag in a `CASE` expression and added explicit column aliases. The corrected query returned the debt and equity totals.

## Failure 2
Question:
Which three BDCs contributed most to that change?

What went wrong: The follow-up first attempted to select `h.period_role` after joining `holdings_v` to `filings`; the view contains current schedules only, so the execute trace returned `invalid: no such column: h.period_role`.

What fixed it: The repair queried the base `holdings` table, where both `prior` and `current` rows exist, and used conditional sums to calculate each BDC's change.

## Failure 3
Question:
Which five BDCs had the largest percentage decline in total fair value between schedules?

What went wrong: The first SQL selected a computed `pct_change` directly from `holdings_v` after grouping by BDC; the column is not stored in the view, so the execute trace returned `invalid: no such column: pct_change`.

What fixed it: The repair used a CTE to aggregate prior and current fair value first, then calculated the percentage in the outer query and filtered out schedules without positive prior values.
