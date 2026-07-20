# TD Variable Rate Mortgage

Maps to `LiabilityType.MORTGAGE`. `Liability.interest_rate` should be understood as a snapshot — the actual rate floats with TD's Mortgage Prime Rate over the life of the term.

## How It Works
The rate is set as TD Mortgage Prime Rate ± a spread, and moves whenever TD's Mortgage Prime Rate changes.
- **TD Prime Rate (current):** 4.45%
- **TD Mortgage Prime Rate (current):** 4.60%
(As of the last BoC-linked adjustment, effective 2025-10-29, down 0.25% from 4.70%.)

Two payment structures:
- **Variable Closed (most common):** payment amount typically stays fixed; as Prime moves, the split between principal and interest shifts (more to principal when Prime falls, more to interest when Prime rises). At renewal, payment may need to be adjusted to keep the amortization schedule on track if Prime moved significantly during the term.
- **Variable Open:** payment and rate both float, with full prepayment flexibility (no penalty to pay off early) — trades a materially higher rate for full flexibility.

## Terms & Indicative Rates (as of mid-July 2026)
| Term | Posted Rate | Special/Discounted Rate |
|---|---|---|
| 5 year variable closed | 4.60% (= current Mortgage Prime) | 4.29% |

*TD's own live rate table is JavaScript-rendered and couldn't be scraped directly — figures above come from a third-party aggregator and wowa.ca's prime-rate tracker; treat as directional and reverify before client-facing use.*

## Who This Fits
Clients comfortable with payment/rate uncertainty in exchange for typically lower starting rates and historically better average cost over a full term — and clients who want the flexibility to convert to a fixed rate mid-term if conditions change (subject to conditions). Less suited to a client who's budget-constrained or rate-anxious; pair with `fixed_rate_mortgage.md` as the natural contrast when framing the conversation.

## Sources
- [Variable Mortgage Rates - TD Canada Trust](https://www.td.com/ca/en/personal-banking/products/mortgages/variable-rate-mortgages)
- [Fixed vs. Variable Rate Mortgages - TD Canada Trust](https://www.td.com/ca/en/personal-banking/advice/borrowing/fixed-vs-variable-rate-mortgages)
- [TD Prime Rates July 2026 | WOWA.ca](https://wowa.ca/td-prime-rate)

*Last verified: 2026-07-18. Prime Rate changes with Bank of Canada policy decisions — reverify the current rate before any client-facing conversation, not just at doc-refresh time.*
