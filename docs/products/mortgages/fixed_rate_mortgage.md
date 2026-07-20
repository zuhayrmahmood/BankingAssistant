# TD Fixed Rate Mortgage

Maps to `LiabilityType.MORTGAGE`. `Liability.interest_rate` is locked for the full term; `Liability.renewal_date` is when the term (not necessarily the amortization) ends.

## How It Works
The interest rate — and therefore the principal + interest payment — is locked for the chosen term and does not change, regardless of what happens to TD's Prime Rate during that period.

## Terms Offered
6 month, 1, 2, 3, 4, 5, 6, 7, or 10 years (amortization can extend up to 25–30 years depending on down payment/insurance status; the *term* is the rate lock-in period, renewed at expiry).

## Indicative Posted Rates (as of mid-July 2026)
| Term | Posted Rate | Special/Discounted Rate |
|---|---|---|
| 1 year fixed closed | 5.49% | — |
| 2 year fixed closed | 4.89% | — |
| 3 year fixed closed | 6.05% | 4.69% |
| 4 year fixed closed | 5.99% | — |
| 5 year fixed closed | 6.09% | 4.84% |

*TD's own live rate table is JavaScript-rendered and could not be scraped directly — these figures come from a third-party rate aggregator (NerdWallet Canada) and should be treated as directional only. TD's "posted" rate is a pre-discount sticker rate; most clients negotiate a lower "special" rate — the gap between posted and special can be well over 1 percentage point, so never quote the posted rate as what a client will actually pay.*

## Who This Fits
Clients who want payment certainty and are risk-averse to rate increases — often first-time homebuyers or anyone on a tight budget where a payment increase would cause real strain. When a client's `Liability` record shows a `MORTGAGE` with a `renewal_date` approaching, that's a clear, time-boxed conversation trigger: renewal is when the client can re-shop rate and term without breaking the mortgage.

## Sources
- [Fixed Rate Mortgages | TD Canada Trust](https://www.td.com/ca/en/personal-banking/products/mortgages/fixed-rate-mortgages)
- [Mortgages Rates - TD Canada Trust](https://www.td.com/ca/en/personal-banking/products/mortgages/mortgage-rates)
- [TD Mortgage Rates - NerdWallet Canada](https://www.nerdwallet.com/ca/p/best/mortgages/td-mortgage-rates)

*Last verified: 2026-07-18. Mortgage rates move frequently with bond yields and BoC policy — always reverify before any client-facing number.*
