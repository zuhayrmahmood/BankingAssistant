# TD High Interest TFSA Savings Account

Maps to `AccountType.HIGH_INTEREST_TFSA`.

## Monthly Fee
- **$0** — no monthly fee.

## Interest Rate
- **0.300%** flat on all daily closing balances (uniform across balance tiers — no tiering).

## Structure
- This is a **TFSA registered plan** that holds a high-interest savings account inside the tax-sheltered wrapper. The same TFSA plan can also hold TD GICs, giving the client flexibility to split between liquid savings and locked-in terms without opening a separate registered account.
- Corresponds to `InvestmentWrapper.TFSA` when the underlying holding is a GIC rather than cash savings — i.e., a client's TFSA contribution room can be split between this savings account and a GIC investment under the same wrapper.

## Contribution Limits
- **2026 annual TFSA contribution limit: $7,000** (federally set, subject to change yearly).
- Unused contribution room carries forward indefinitely.
- Over-contribution is subject to a **1% per month penalty tax** on the excess (CRA rule, not TD-specific).

## Transactions
- Unlimited free online transfers to other TD deposit accounts.

## Who This Fits
Any client without a TFSA at all is a standing-out gap — the `to_prompt_string()` output already surfaces missing standard products, and TFSA absence is one of the clearest openings for a "have you thought about tax-free growth" conversation. Clients with unused contribution room and idle cash in a non-registered savings account (see `everyday_savings.md`) are a strong pairing to raise together.

## Sources
- [TD High Interest TFSA Savings Account](https://www.td.com/ca/en/personal-banking/products/registered-plans/tfsa/savings-accounts/tfsa-high-interest-savings-account)
- [Bank Account Interest Rates | TD Canada Trust](https://www.td.com/ca/en/personal-banking/products/bank-accounts/account-rates)

*Last verified: 2026-07-18. Interest rate and the annual contribution limit both change (rate periodically, contribution limit annually via CRA) — reverify before quoting exact numbers to a client.*
