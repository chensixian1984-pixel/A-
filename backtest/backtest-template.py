#!/usr/bin/env python3
"""
交易台回测模板（策略师用）
- 输入：CSV，列 date,open,high,low,close,volume，至少 3 年日线数据
- 规则：由策略师按每个形态写出精确的入场价、止损、目标价和仓位，
  在 run_backtest() 里把同一套规则写成信号函数，不要为每个标的手调参数
- 成本：佣金 0.025%（每笔最低 5 元）、卖出印花税 0.05%、过户费 0.001%，
  滑点默认每边 0.1%，可在参数里改，但必须在报告里写明
- 持仓：波段 2-10 天，止损 / 目标价先到先出，超时按第 10 天收盘出
- 否决标准：交易次数 <30 次、最近一年不赚钱、只在某一个特定参数下才成立
用法：python3 backtest-template.py --csv data.csv --out report.json
  数据来源、时间戳和参数必须写进报告，缺数据就直说缺了，不要编数据。
"""
import argparse, json
import pandas as pd
import numpy as np

COMMISSION = 0.00025      # 佣金 0.025%，每笔最低 5 元
STAMP_DUTY = 0.0005       # 卖出印花税 0.05%
TRANSFER_FEE = 0.00001    # 过户费 0.001%
SLIPPAGE = 0.001          # 滑点，每边 0.1%


def load_prices(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns), "CSV 缺少 OHLCV 列"
    return df


def signal(df: pd.DataFrame, i: int) -> bool:
    """策略师在这里写规则：返回 True 表示在第 i 根 K 线收盘后入场。
    示例是占位规则（不要直接用它交差）：收盘价站上 50 日均线且成交量大于 20 日均量。
    规则必须和提交给风控的入场价 / 止损 / 目标价是同一套。"""
    if i < 50:
        return False
    ma50 = df["close"].iloc[i - 50:i].mean()
    vol20 = df["volume"].iloc[i - 20:i].mean()
    return df["close"].iloc[i] > ma50 and df["volume"].iloc[i] > vol20


def run_backtest(df: pd.DataFrame, entry_offset=0.0, stop_pct=0.05, target_pct=0.10,
                 max_hold=10, capital=10000.0, slippage=SLIPPAGE):
    """entry_offset: 入场价相对信号收盘价的偏移（滑点外）；stop/target 为相对入场价的比例。
    仓位按交易台规矩：单笔最多亏 1% 总资金，据此倒推股数（100 股一手，向下取整）。"""
    trades = []
    i = 0
    equity = capital
    peak = capital
    max_dd = 0.0
    while i < len(df) - 1:
        if not signal(df, i):
            i += 1
            continue
        entry = df["close"].iloc[i] * (1 + entry_offset + slippage)
        stop = entry * (1 - stop_pct)
        target = entry * (1 + target_pct)
        # 单笔最多亏 1% 总资金：股数 = 1% * equity / (entry - stop)，向下取整到 100 股
        risk_per_share = entry - stop
        shares = int((0.01 * equity) // risk_per_share // 100 * 100) if risk_per_share > 0 else 0
        if shares <= 0:
            i += 1
            continue
        cost = entry * shares
        buy_fee = max(cost * COMMISSION, 5) + cost * TRANSFER_FEE
        exit_price, exit_reason, exit_day = None, "hold_expired", min(i + max_hold, len(df) - 1)
        for j in range(i + 1, min(i + max_hold, len(df)) + 1):
            if j >= len(df):
                break
            if df["low"].iloc[j] <= stop:
                exit_price, exit_reason, exit_day = stop * (1 - slippage), "stop", j
                break
            if df["high"].iloc[j] >= target:
                exit_price, exit_reason, exit_day = target * (1 - slippage), "target", j
                break
        if exit_price is None:
            exit_price = df["close"].iloc[exit_day] * (1 - slippage)
        proceeds = exit_price * shares
        sell_fee = max(proceeds * COMMISSION, 5) + proceeds * TRANSFER_FEE + proceeds * STAMP_DUTY
        pnl = proceeds - cost - buy_fee - sell_fee
        equity += pnl
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)
        trades.append({
            "entry_date": str(df["date"].iloc[i].date()),
            "exit_date": str(df["date"].iloc[exit_day].date()),
            "entry": round(entry, 2), "exit": round(exit_price, 2),
            "shares": shares, "pnl": round(pnl, 2), "reason": exit_reason,
        })
        i = exit_day + 1
    return trades, equity, max_dd


def report(trades, equity, max_dd, capital=10000.0):
    t = pd.DataFrame(trades)
    if t.empty:
        return {"trades": 0, "note": "无交易：信号没有触发或数据不足"}
    wins = t[t["pnl"] > 0]
    losses = t[t["pnl"] <= 0]
    last_year = t[pd.to_datetime(t["exit_date"]) >= pd.to_datetime(t["exit_date"]).max() - pd.Timedelta(days=365)]
    return {
        "trades": int(len(t)),
        "win_rate": round(len(wins) / len(t), 4),
        "avg_win": round(wins["pnl"].mean(), 2) if len(wins) else 0.0,
        "avg_loss": round(losses["pnl"].mean(), 2) if len(losses) else 0.0,
        "total_pnl": round(t["pnl"].sum(), 2),
        "final_equity": round(equity, 2),
        "max_drawdown": round(max_dd, 4),
        "last_year_trades": int(len(last_year)),
        "last_year_pnl": round(last_year["pnl"].sum(), 2) if len(last_year) else 0.0,
        "reject": bool(len(t) < 30 or (len(last_year) and last_year["pnl"].sum() <= 0)),
        "reject_reason": ("交易次数少于 30 次" if len(t) < 30 else
                          "最近一年不赚钱" if len(last_year) and last_year["pnl"].sum() <= 0 else ""),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--stop", type=float, default=0.05)
    ap.add_argument("--target", type=float, default=0.10)
    args = ap.parse_args()
    df = load_prices(args.csv)
    trades, equity, max_dd = run_backtest(df, stop_pct=args.stop, target_pct=args.target)
    r = report(trades, equity, max_dd)
    r["data_range"] = f"{df['date'].iloc[0].date()} 至 {df['date'].iloc[-1].date()}，{len(df)} 个交易日"
    r["costs"] = {"commission": COMMISSION, "stamp_duty_sell": STAMP_DUTY,
                  "transfer_fee": TRANSFER_FEE, "slippage_per_side": SLIPPAGE}
    print(json.dumps(r, ensure_ascii=False, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"report": r, "trades": trades}, f, ensure_ascii=False, indent=2)
