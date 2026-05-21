# Current vs grid50_best with Regime Gate - 2026-05-20

Gate tested:

`regime_gate:max_ema_spread_bps=50:max_adx=35:unsafe_action=reduce:unsafe_size_scale=0.5`

Execution:

- Profile: `mainnet-like`
- Latency: `0.3s`
- Risk caps enabled
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT, LTCUSDT
- Initial equity: `30,000` USDT

## Strategy Definitions

Archived `current`:

- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=30,inner_step_bps=15,max_trend_bps=30)`
- Margin/order: `66` USDT
- TP: `100` bps
- Account cap: `50,000` USDT
- Symbol cap: `10,000` USDT

`grid50_best`:

- Signal: `trend_filter(inner=grid,inner_anchor_period=200,inner_entry_bps=50,inner_step_bps=25,max_trend_bps=20)`
- Margin/order: `100` USDT
- TP: `75` bps
- Account cap: `12,500` USDT
- Symbol cap: `4,000` USDT

## Results

| Window | Strategy + gate | Realistic annual ROI | ROI | Max DD | Trades | Target >= 12% | Safety DD <= 25% |
|---|---|---:|---:|---:|---:|:---:|:---:|
| `2022-05-09` to `2023-10-30` | archived current | `4.47%` | `6.60%` | `17.47%` | `188` | no | yes |
| `2022-05-09` to `2023-10-30` | grid50_best | `12.68%` | `18.73%` | `10.17%` | `663` | yes | yes |
| `2024-10-30` to `2026-02-02` | archived current | `15.10%` | `19.03%` | `26.31%` | `523` | yes | no |
| `2024-10-30` to `2026-02-02` | grid50_best | `11.26%` | `14.19%` | `14.45%` | `452` | no | yes |

## Read

`grid50_best + regime_gate` is better for the sideways/choppy window. It clears
the `12%` annual target and keeps drawdown near `10%`.

Archived `current + regime_gate` performs better on the trend-mix window, but
the drawdown reaches `26.31%`, which breaches the configured optimizer safety
gate of `25%`. That means it is not acceptable as-is, even though ROI is higher.

Recommendation: keep `grid50_best` as the safer default. Do not switch back to
archived `current` without reducing its exposure cap or adding a hard DD/position
control.

## Reports

- `reports/compare_execution_2022_05_09_to_2023_10_30_current_regime_reduce50_ema50_adx35_mainnet_like.md`
- `reports/compare_execution_2022_05_09_to_2023_10_30_grid50_regime_reduce50_ema50_adx35_mainnet_like.md`
- `reports/compare_execution_2024_10_30_to_2026_02_02_current_regime_reduce50_ema50_adx35_mainnet_like.md`
- `reports/compare_execution_2024_10_30_to_2026_02_02_grid50_regime_reduce50_ema50_adx35_mainnet_like.md`
