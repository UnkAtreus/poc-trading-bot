# Crash Option Sweep - 2026 YTD

- Date range: `2026-01-01` to `2026-05-02`
- Initial equity: `30,000 USDT`
- BTC stress target: `48,000`
- Raw CSV: `logs/crash_option_sweep_2026_ytd.csv`

## V1 vs V2 Check

They are **not the same**, so they should not be combined.

| Version | Signal | Margin/order | Status |
|---|---|---:|---|
| v1 | `trend_filter(grid anchor=200, max_trend=30)` | 66 | Historical 2025 setup |
| v2 | `trend_filter(grid anchor=100, max_trend=15)` | 114 | Current baseline |
| v2_crash_guard | v2 wrapped with BTC crash long-blocker | 114 | Experimental |

## Final Recommendation

No tested option achieved both:

- `>= 6%` 2026 YTD ROI, and
- 60% full-cap crash loss `<= 30%` of equity.

The selected practical option is `v2_crash_guard_cap20_global4560`, saved as
`reports/strategies/v3_crash_balanced.md`. It keeps the 2026 YTD target while
cutting the full-cap 60% crash loss from `30,000` to `12,000`.

| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_crash_guard_cap20_global4560 | 1,803.40 | 6.01% | 9.59% | 20,000 | 12,000 | 26,757.55 | 7 | 97 | 100.00% | yes | no |

The stricter crash-first option is `v2_crash_guard_cap15_global3420`: it keeps
60% full-cap crash loss to `9,000`, but missed the 2026 YTD target at `5.58%`
ROI.

## Highest ROI

| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_crash_guard_cap50_global10 | 2,047.68 | 6.83% | 11.08% | 50,000 | 30,000 | 26,423.27 | 7 | 103 | 100.00% | yes | no |
| v2_crash_guard_cap30_global6 | 2,047.68 | 6.83% | 11.08% | 30,000 | 18,000 | 26,423.27 | 7 | 103 | 100.00% | yes | no |
| v2_cap50_global10 | 1,803.52 | 6.01% | 11.03% | 50,000 | 30,000 | 26,141.94 | 7 | 92 | 100.00% | yes | no |
| v2_cap30_global6 | 1,803.52 | 6.01% | 11.03% | 30,000 | 18,000 | 26,141.94 | 7 | 92 | 100.00% | yes | no |
| v2_crash_guard_cap20_global4560 | 1,803.40 | 6.01% | 9.59% | 20,000 | 12,000 | 26,757.55 | 7 | 97 | 100.00% | yes | no |
| v2_crash_guard_cap15_global3420 | 1,675.39 | 5.58% | 8.37% | 15,000 | 9,000 | 27,208.58 | 7 | 97 | 100.00% | no | yes |
| v2_cap20_global4560 | 1,559.24 | 5.20% | 9.70% | 20,000 | 12,000 | 26,476.22 | 7 | 86 | 100.00% | no | no |
| v2_cap15_global3420 | 1,442.85 | 4.81% | 8.52% | 15,000 | 9,000 | 26,938.88 | 7 | 86 | 100.00% | no | yes |
| v2_crash_guard_cap20_balanced | 1,268.32 | 4.23% | 6.87% | 20,000 | 12,000 | 28,591.17 | 5 | 90 | 100.00% | no | no |
| v2_crash_guard_cap15_balanced | 1,256.69 | 4.19% | 6.87% | 15,000 | 9,000 | 28,579.55 | 5 | 90 | 100.00% | no | yes |

## Safest Caps

| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_crash_guard_cap12500_global2280 | 1,093.80 | 3.65% | 6.09% | 12,500 | 7,500 | 28,845.98 | 5 | 87 | 100.00% | no | yes |
| v2_cap12500_global2280 | 1,047.30 | 3.49% | 6.60% | 12,500 | 7,500 | 27,553.14 | 7 | 83 | 100.00% | no | yes |
| v1_cap12500_global2280 | 660.16 | 2.20% | 6.55% | 12,500 | 7,500 | 27,453.05 | 6 | 62 | 100.00% | no | yes |
| v2_crash_guard_cap15_global3420 | 1,675.39 | 5.58% | 8.37% | 15,000 | 9,000 | 27,208.58 | 7 | 97 | 100.00% | no | yes |
| v2_cap15_global3420 | 1,442.85 | 4.81% | 8.52% | 15,000 | 9,000 | 26,938.88 | 7 | 86 | 100.00% | no | yes |
| v2_crash_guard_cap15_balanced | 1,256.69 | 4.19% | 6.87% | 15,000 | 9,000 | 28,579.55 | 5 | 90 | 100.00% | no | yes |
| v2_cap15_balanced | 1,210.19 | 4.03% | 7.66% | 15,000 | 9,000 | 27,286.71 | 7 | 86 | 100.00% | no | yes |
| v1_cap15_global3420 | 728.62 | 2.43% | 6.55% | 15,000 | 9,000 | 27,521.51 | 6 | 70 | 100.00% | no | yes |
| v1_cap15_balanced | 673.62 | 2.25% | 6.55% | 15,000 | 9,000 | 27,466.51 | 6 | 62 | 100.00% | no | yes |
| v2_crash_guard_cap20_global4560 | 1,803.40 | 6.01% | 9.59% | 20,000 | 12,000 | 26,757.55 | 7 | 97 | 100.00% | yes | no |

## All Cases

| Case | Net PnL | ROI | Max DD | Account cap | 60% cap loss | Market BTC48 equity | Open syms | Trades | Win rate | Target? | Safe cap? |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v1_cap50_global10 | 752.21 | 2.51% | 6.55% | 50,000 | 30,000 | 27,543.63 | 7 | 73 | 100.00% | no | no |
| v1_cap30_global6 | 752.21 | 2.51% | 6.55% | 30,000 | 18,000 | 27,543.63 | 7 | 73 | 100.00% | no | no |
| v1_cap20_global4560 | 749.06 | 2.50% | 6.55% | 20,000 | 12,000 | 27,542.19 | 7 | 73 | 100.00% | no | no |
| v1_cap15_global3420 | 728.62 | 2.43% | 6.55% | 15,000 | 9,000 | 27,521.51 | 6 | 70 | 100.00% | no | yes |
| v1_cap12500_global2280 | 660.16 | 2.20% | 6.55% | 12,500 | 7,500 | 27,453.05 | 6 | 62 | 100.00% | no | yes |
| v1_cap15_balanced | 673.62 | 2.25% | 6.55% | 15,000 | 9,000 | 27,466.51 | 6 | 62 | 100.00% | no | yes |
| v1_cap20_balanced | 673.62 | 2.25% | 6.55% | 20,000 | 12,000 | 27,466.51 | 6 | 62 | 100.00% | no | no |
| v2_cap50_global10 | 1,803.52 | 6.01% | 11.03% | 50,000 | 30,000 | 26,141.94 | 7 | 92 | 100.00% | yes | no |
| v2_cap30_global6 | 1,803.52 | 6.01% | 11.03% | 30,000 | 18,000 | 26,141.94 | 7 | 92 | 100.00% | yes | no |
| v2_cap20_global4560 | 1,559.24 | 5.20% | 9.70% | 20,000 | 12,000 | 26,476.22 | 7 | 86 | 100.00% | no | no |
| v2_cap15_global3420 | 1,442.85 | 4.81% | 8.52% | 15,000 | 9,000 | 26,938.88 | 7 | 86 | 100.00% | no | yes |
| v2_cap12500_global2280 | 1,047.30 | 3.49% | 6.60% | 12,500 | 7,500 | 27,553.14 | 7 | 83 | 100.00% | no | yes |
| v2_cap15_balanced | 1,210.19 | 4.03% | 7.66% | 15,000 | 9,000 | 27,286.71 | 7 | 86 | 100.00% | no | yes |
| v2_cap20_balanced | 1,233.44 | 4.11% | 7.66% | 20,000 | 12,000 | 27,309.96 | 7 | 86 | 100.00% | no | no |
| v2_crash_guard_cap50_global10 | 2,047.68 | 6.83% | 11.08% | 50,000 | 30,000 | 26,423.27 | 7 | 103 | 100.00% | yes | no |
| v2_crash_guard_cap30_global6 | 2,047.68 | 6.83% | 11.08% | 30,000 | 18,000 | 26,423.27 | 7 | 103 | 100.00% | yes | no |
| v2_crash_guard_cap20_global4560 | 1,803.40 | 6.01% | 9.59% | 20,000 | 12,000 | 26,757.55 | 7 | 97 | 100.00% | yes | no |
| v2_crash_guard_cap15_global3420 | 1,675.39 | 5.58% | 8.37% | 15,000 | 9,000 | 27,208.58 | 7 | 97 | 100.00% | no | yes |
| v2_crash_guard_cap12500_global2280 | 1,093.80 | 3.65% | 6.09% | 12,500 | 7,500 | 28,845.98 | 5 | 87 | 100.00% | no | yes |
| v2_crash_guard_cap15_balanced | 1,256.69 | 4.19% | 6.87% | 15,000 | 9,000 | 28,579.55 | 5 | 90 | 100.00% | no | yes |
| v2_crash_guard_cap20_balanced | 1,268.32 | 4.23% | 6.87% | 20,000 | 12,000 | 28,591.17 | 5 | 90 | 100.00% | no | no |
