# TD e-Series Index Funds

Maps to `InvestmentType.MUTUAL_FUND`. `MutualFundDetails.mer` is notably low for this product family relative to TD's actively-managed funds.

## What It Is
TD's low-cost, no-load index fund family, designed for investors who transact electronically (including via discount brokerage) rather than through an advisor relationship. Each fund tracks a market index rather than being actively managed.

## Key Fee Advantage
- **TD Canadian Index e-Series MER: 0.33%**, versus **2.00%+** typical for actively-managed equity mutual funds — a materially large savings compounded over a long holding period.
- No-load: no sales charges on purchase or redemption (subject to the standard short-term trading fee if switched/redeemed within 30 days of purchase — see `mutual_fund_fee_structures.md`).

## Who This Fits
The go-to recommendation for a cost-conscious, self-directed client (or one being coached toward self-direction) who doesn't want to pay for active management or an advisor relationship — particularly relevant when a client's existing `Investment` holding shows a high MER relative to its returns, since switching into e-Series is a concrete, quantifiable "we can lower your fees" conversation. Less suited to clients who want the hand-holding of TD Comfort Portfolios or a personal banker/financial planner relationship (see `assistant.py`'s value-creation framing: `dspy` signature notes financial planner engagement applies over $100k total balance, personal banker under $100k — e-Series clients often self-serve regardless of balance).

## Sources
- [TD e-Series Funds: Reduce Your Investment Fees](https://maplemoney.com/td-e-series/)
- [Mutual Fund Fees | TD Asset Management](https://www.td.com/ca/en/asset-management/how-to/mutual-fund-fees)

*Last verified: 2026-07-18. MER figures are quoted from a third-party source for the flagship fund only — confirm exact current MER per specific e-Series fund before quoting a client.*
