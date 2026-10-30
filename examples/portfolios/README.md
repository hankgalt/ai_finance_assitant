# Example portfolio imports

These files contain synthetic positions and prices for exercising the Portfolio Dashboard. They are not current market data, recommendations, or examples of suitable allocations.

## Import workflow

1. Open **Portfolio** and select **JSON / CSV / XLSX**.
2. Enter any portfolio label, choose one example file, and select **Validate import**.
3. Review the findings. Each example should be accepted without blocking findings.
4. Select **Save validated portfolio**, then select **Analyze** from Saved portfolios.
5. Verify the holding values, allocation chart and table, classification coverage, expense coverage, and diversification output.

The application assigns the Portfolio identifier, label, base currency, and import time. The files contain only Account and Holding rows. Analysis intentionally reports `USER_PRICE_USED` because every example carries an explicit synthetic price instead of calling a market-data provider.

## Files

- `balanced_multi_account.json`: seven ETF positions across taxable, traditional IRA, and Roth IRA Accounts. Useful for checking multiple Accounts, allocation, classifications, expense coverage, and diversification.
- `concentrated_technology.csv`: four individual stocks plus a cash position in one taxable Account. Useful for checking concentrated allocation and partial expense-ratio coverage.
- `retirement_income.xlsx`: seven ETF positions across traditional IRA, Roth IRA, and HSA Accounts. Useful for checking XLSX parsing, Account grouping, and income-oriented asset classifications.

All prices are synthetic values observed at `2026-10-29T12:00:00Z`. Expense ratios use decimal fractions: `0.0003` means `0.03%`.
