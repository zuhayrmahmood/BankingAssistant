# TD Mutual Fund Fee Structures (Reference)

General reference for interpreting `MutualFundDetails.mer` on any `InvestmentType.MUTUAL_FUND` holding — not a specific product, but the mechanics behind how mutual fund costs work at TD.

## Management Expense Ratio (MER)
- The MER is **not charged directly** to the investor — it's baked into the fund's net return, so a client won't see it as a line-item deduction, only as a lower return than the fund's gross performance.
- MER is made up of:
  - Portfolio management fees (research, security selection, risk management)
  - Trailing commissions (ongoing advisor compensation)
  - Operating costs (accounting, audit, record-keeping)
  - Applicable taxes (GST/QST/HST)
- **Index funds have materially lower MERs** than actively-managed funds since there's no active research/selection cost — see `td_eseries_index_funds.md` (0.33%) vs. actively-managed equity funds (2.00%+).

## Sales Charge (Load) Options
| Load Type | How It Works |
|---|---|
| No Load | No sales charge at purchase or redemption |
| Front-End Load | Charged at purchase, paid to the advisor for providing advice |
| Back-End Load (DSC) | Charged at redemption/sale, paid to the fund company |

## Fee-Based (F-Series) Funds
For clients in a fee-based advisory relationship, TD offers F-Series funds where the advice fee is negotiated separately from the fund's own charges — and that separately-negotiated advice fee **may be tax-deductible** (non-registered accounts), unlike an MER embedded in a standard series fund.

## Short-Term Trading Fee
Applied if a client switches or redeems within:
- **7 days** of purchase for standard mutual funds
- **30 days** of purchase for index funds (e.g. e-Series)
This exists to discourage short-term trading of what's meant to be a long-term holding — worth mentioning to a client who asks about flexibility/liquidity before investing.

## Why This Matters for Client Conversations
A client's `Investment.details.mer` field (for `MUTUAL_FUND` type) is one of the more actionable data points in a client's profile — a high MER relative to a plain index alternative is a concrete, defensible reason to suggest a review, distinct from performance-chasing.

## Sources
- [Mutual Fund Fees | TD Asset Management](https://www.td.com/ca/en/asset-management/how-to/mutual-fund-fees)

*Last verified: 2026-07-18. Structural/mechanical information — less likely to go stale than specific rate figures, but reverify short-term trading fee windows and F-Series eligibility rules periodically.*
