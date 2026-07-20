# TD Non-Redeemable (Non-Cashable) GIC

Maps to `InvestmentType.GIC` with `GICDetails.interest_rate` set at issue and locked for the term.

## How It Works
Funds are locked in for the full term — no early withdrawal. In exchange, non-redeemable GICs pay a **higher fixed rate** than the cashable equivalent.

## Terms & Minimums
- Terms: 30 days to 5 years (short-term: 30/60/90/120/180/270 days; long-term: 1/2/3/4/5 years)
- Minimum investment: **$500**
- Available in TFSA, RRSP, RRIF, RESP, FHSA, and non-registered plans
- Simple or compound interest options on longer terms

## Indicative Rates (CAD, as of mid-July 2026)
| Term | Rate |
|---|---|
| 1 year | 2.70% |
| 2 years | 2.80% |
| 3 years | 2.85% |
| 4 years | 2.90% |
| 5 years | 3.10% |

*Rates sourced from a third-party rate aggregator (NerdWallet Canada), not TD's own live rate table, which is JavaScript-rendered and could not be scraped directly. Treat these as directional only — confirm exact current rates at td.com or 1-800-386-3757 before quoting a client.*

## Who This Fits
For the `Investment` dataclass in this codebase, this is the most common `InvestmentType.GIC` product. Suited to clients with idle cash they won't need for the term length and who prioritize the guaranteed rate over liquidity — e.g., cash sitting in `everyday_savings.md` or `epremium.md` earning near-zero interest with no near-term spending need. Longer terms pay more, so understanding the client's actual time horizon (not just defaulting to 1-year) is the key qualifying question.

## Sources
- [Non-Cashable GIC Rates | TD Canada Trust](https://www.td.com/ca/en/personal-banking/personal-investing/products/gic/non-cashable-gic-rates)
- [Investing in Non-Cashable GICs | TD Canada Trust](https://www.td.com/ca/en/personal-banking/personal-investing/products/gic/non-cashable-gic)
- [Compare TD GIC Rates for June 2026 - NerdWallet Canada](https://www.nerdwallet.com/ca/p/best/banking/best-td-gic-rates)

*Last verified: 2026-07-18. GIC rates move with the Bank of Canada rate cycle — reverify before client-facing use.*
