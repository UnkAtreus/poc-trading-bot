from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


def signal_full_label(name: str, params: Mapping[str, Any] | None = None) -> str:
    """CLI-style signal spec with every parameter preserved."""
    clean_name = str(name or "").strip()
    clean_params = _dict_params(params)
    if not clean_params:
        return clean_name
    return f"{clean_name}:" + ":".join(f"{key}={value}" for key, value in clean_params.items())


def signal_short_label(name: str, params: Mapping[str, Any] | None = None) -> str:
    """Readable compact label for tables, archive indexes, and generated reports."""
    clean_name = str(name or "").strip()
    clean_params = _dict_params(params)
    if not clean_params:
        return _slug(clean_name)

    if clean_name == "trend_filter" and clean_params.get("inner") == "grid":
        return _join_parts(
            [
                "trend_grid",
                _part("a", clean_params.get("inner_anchor_period")),
                _part("e", clean_params.get("inner_entry_bps")),
                _part("s", clean_params.get("inner_step_bps")),
                _part("t", clean_params.get("max_trend_bps")),
            ]
        )
    if clean_name == "regime_gate":
        return _join_parts(
            [
                _regime_inner_label(clean_params),
                _part("ema", clean_params.get("max_ema_spread_bps")),
                _part("adx", clean_params.get("max_adx")),
                _regime_action_label(clean_params),
            ]
        )
    if clean_name == "trend_filter" and clean_params.get("inner") == "bollinger_bands":
        return _join_parts(
            [
                "trend_bb",
                _part("p", clean_params.get("inner_period")),
                _part("std", clean_params.get("inner_num_std")),
                _part("t", clean_params.get("max_trend_bps")),
            ]
        )
    if clean_name == "trend_filter" and clean_params.get("inner") == "zscore":
        return _join_parts(
            [
                "trend_z",
                _part("p", clean_params.get("inner_period")),
                _part("th", clean_params.get("inner_threshold")),
                _part("t", clean_params.get("max_trend_bps")),
            ]
        )
    if clean_name == "grid":
        return _join_parts(
            [
                "grid",
                _part("a", clean_params.get("anchor_period") or clean_params.get("inner_anchor_period")),
                _part("e", clean_params.get("entry_bps") or clean_params.get("inner_entry_bps")),
                _part("s", clean_params.get("step_bps") or clean_params.get("inner_step_bps")),
            ]
        )
    if clean_name == "bollinger_bands":
        return _join_parts(
            [
                "bb",
                _part("p", clean_params.get("period")),
                _part("std", clean_params.get("num_std")),
            ]
        )
    if clean_name == "zscore":
        return _join_parts(
            [
                "z",
                _part("p", clean_params.get("period")),
                _part("th", clean_params.get("threshold")),
            ]
        )
    if clean_name == "ema_crossover":
        return _join_parts(
            [
                "ema",
                _part("f", clean_params.get("fast_period") or clean_params.get("ema_fast")),
                _part("s", clean_params.get("slow_period") or clean_params.get("ema_slow")),
            ]
        )

    return _generic_short_label(clean_name, clean_params)


def _generic_short_label(name: str, params: Mapping[str, Any]) -> str:
    aliases = {
        "inner": "",
        "inner_anchor_period": "a",
        "anchor_period": "a",
        "inner_entry_bps": "e",
        "entry_bps": "e",
        "inner_step_bps": "s",
        "step_bps": "s",
        "max_trend_bps": "t",
        "max_ema_spread_bps": "ema",
        "max_adx": "adx",
        "unsafe_action": "act",
        "unsafe_size_scale": "scale",
        "period": "p",
        "inner_period": "p",
        "num_std": "std",
        "inner_num_std": "std",
        "threshold": "th",
        "inner_threshold": "th",
        "tp_offset_bps": "tp",
        "btc_drop_bps": "drop",
    }
    parts = [_slug(name)]
    for key, value in params.items():
        if value is None:
            continue
        prefix = aliases.get(str(key), _slug(str(key)))
        if prefix:
            parts.append(_part(prefix, value))
        else:
            parts.append(_slug(str(value)))
        if len(parts) >= 7:
            break
    return _join_parts(parts)


def _dict_params(params: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(params, Mapping):
        return {}
    return {str(key): params[key] for key in params}


def _part(prefix: str, value: Any) -> str | None:
    if value is None:
        return None
    return f"{prefix}{_slug_value(value)}"


def _join_parts(parts: list[str | None]) -> str:
    return "_".join(part for part in parts if part)


def _regime_inner_label(params: Mapping[str, Any]) -> str:
    inner = str(params.get("inner") or "").strip()
    if inner == "trend_filter" and params.get("inner_inner") == "grid":
        return _join_parts(
            [
                "rg_trend_grid",
                _part("a", params.get("inner_inner_anchor_period")),
                _part("e", params.get("inner_inner_entry_bps")),
                _part("s", params.get("inner_inner_step_bps")),
                _part("t", params.get("inner_max_trend_bps")),
            ]
        )
    if inner == "grid":
        return _join_parts(
            [
                "rg_grid",
                _part("a", params.get("inner_anchor_period")),
                _part("e", params.get("inner_entry_bps")),
                _part("s", params.get("inner_step_bps")),
            ]
        )
    return _join_parts(["rg", _slug(inner or "inner")])


def _regime_action_label(params: Mapping[str, Any]) -> str | None:
    action = str(params.get("unsafe_action") or "pause").strip()
    if action == "reduce":
        return _part("reduce", params.get("unsafe_size_scale"))
    if action == "pause":
        return "pause"
    return _slug(action)


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9]+", "_", value.strip())).strip("_")


def _slug_value(value: Any) -> str:
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return _slug(text)
