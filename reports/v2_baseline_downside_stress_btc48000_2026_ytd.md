# V2 Baseline Downside Stress - BTC 48,000

- Strategy: v2 baseline only
- Source state: `logs/v2_baseline_2026_ytd_equity30000.txt`
- Source period: `2026-01-01` to `2026-05-02`
- Initial equity: 30,000 USDT
- Realized net PnL before shock: 1,803.52 USDT
- Stress target: BTCUSDT = 48,000
- BTC last close used: 78,189.30
- BTC shock: -38.61%

This stress uses the open `MERGE_PENDING` positions at the end of the 2026 YTD
baseline run. It assumes the open crypto positions are long, which is consistent
with their BEP being above the latest close.

## Open Positions Before Shock

| Symbol | Qty | BEP | Last close | Current unrealized |
|---|---:|---:|---:|---:|
| BTCUSDT | 0.027638 | 82,494.7882 | 78,189.3000 | -119.00 |
| ETHUSDT | 0.423733 | 2,690.3741 | 2,294.5800 | -167.71 |
| SOLUSDT | 43.616544 | 104.5475 | 83.7200 | -908.42 |
| XRPUSDT | 629.558031 | 1.8108 | 1.3849 | -268.13 |
| BNBUSDT | 1.319952 | 863.6680 | 615.1000 | -328.10 |
| LTCUSDT | 16.178302 | 70.4647 | 55.3700 | -244.21 |
| XAUTUSDT | 0.250056 | 4,558.9783 | 4,600.4000 | +10.36 |

Current open-position unrealized PnL: **-2,025.21 USDT**  
Current stressed equity before shock: **29,778.31 USDT**

## Scenario A - BTC Only Drops To 48,000

Other symbols are unchanged.

| Metric | Value |
|---|---:|
| BTC unrealized PnL at 48,000 | -953.37 USDT |
| Total unrealized PnL | -2,859.58 USDT |
| Account equity after shock | 28,943.94 USDT |
| Equity vs initial 30,000 | -3.52% |
| Extra loss from current mark | -834.37 USDT |

Read: BTC-only downside to 48,000 is not an account-level liquidation problem
if the account is cross/unified and only these positions exist. The BTC open
size is small.

## Scenario B - Market-Wide Crypto Drop Matching BTC

BTC drops to 48,000 and ETH/SOL/XRP/BNB/LTC drop by the same -38.61%.
XAUT is left unchanged.

| Symbol | Shock mark | Unrealized PnL |
|---|---:|---:|
| BTCUSDT | 48,000.0000 | -953.37 |
| ETHUSDT | 1,408.6306 | -543.12 |
| SOLUSDT | 51.3953 | -2,318.32 |
| XRPUSDT | 0.8502 | -604.76 |
| BNBUSDT | 377.6067 | -641.58 |
| LTCUSDT | 33.9914 | -590.08 |
| XAUTUSDT | 4,600.4000 | +10.36 |

| Metric | Value |
|---|---:|
| Total unrealized PnL | -5,640.87 USDT |
| Account equity after shock | 26,162.65 USDT |
| Equity vs initial 30,000 | -12.79% |
| Extra loss from current mark | -3,615.67 USDT |

Read: with cross/unified equity, the account still survives this current-position
stress. The bigger danger is not account equity going to zero from the current
open size; the bigger danger is liquidation mode and future layering during a
waterfall.

## Approx Isolated 10x Liquidation Zones

These are rough long-position zones using `BEP * 0.90`, ignoring maintenance
margin and exchange tiers. Real liquidation prices are usually a little higher.

| Symbol | Rough isolated 10x liq zone |
|---|---:|
| BTCUSDT | 74,245.3094 |
| ETHUSDT | 2,421.3367 |
| SOLUSDT | 94.0927 |
| XRPUSDT | 1.6297 |
| BNBUSDT | 777.3012 |
| LTCUSDT | 63.4182 |
| XAUTUSDT | 4,103.0805 |

Important: if these positions are isolated 10x, BTC at 48,000 is far below the
rough liquidation zone. Several non-BTC positions are also already below their
rough isolated zones in the 2026 YTD final state. Therefore, these backtests
should be read as cross/unified-account mark-to-market tests, not isolated
liquidation-safe tests.

## Max-Cap Warning

The active risk cap allows up to 50,000 USDT account notional. If the bot keeps
adding during a strong downtrend and fills the whole cap long, then a -38.61%
market move is approximately a **19,305 USDT** loss before fees/slippage. That
would leave only about **12,499 USDT** from a 30,000 USDT account plus the
current 1,803.52 USDT realized PnL.

The current open positions are much smaller than the cap, but the cap-level
stress is the real worst-case direction to control next.
