#!/usr/bin/env python3
"""海尔智家 600690 回测：与提交计划同一套规则
信号（收盘后判定，次日开盘入场 - 比模板的信号日收盘入场更保守，无前视）：
  close > SMA50 且 volume > 30日均量 且 close > 5日前收盘价（周内动量）
入场：信号次日开盘价（含滑点 0.1%）
止损：信号日 SMA50 水平（与提交计划一致：止损 = SMA50）
目标：入场价 + 2 x (入场价 - 止损价)，即 2R
出场：止损 / 目标先到先出，最多持仓 3 天，第 3 天收盘出（短线 T+1，2026-11-08 起风格由波段 2-10 天改为短线 1-3 天）
仓位：单笔最多亏总资金 1%，股数向下取整到 100 股；若 100 股的风险已超 1%，不交易
成本：佣金 0.025% 每笔最低 5 元、卖出印花税 0.05%、过户费 0.001%、滑点每边 0.1%
数据：东财前复权日线 2023-11-01 至 2026-11-06，731 个交易日
"""
import argparse, json
import pandas as pd
COMMISSION=0.00025; STAMP=0.0005; TRANSFER=0.00001; SLIP=0.001

def load(path):
    df=pd.read_csv(path, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    df["sma50"]=df["close"].rolling(50).mean()
    df["vol30"]=df["volume"].rolling(30).mean()
    return df

def run(df, target_r=2.0, vol_window=30, mom_days=5, max_hold=3, capital=10000.0):
    df=df.copy()
    if vol_window!=30:
        df["vol30"]=df["volume"].rolling(vol_window).mean()
    trades=[]; equity=capital; peak=capital; max_dd=0.0; i=50
    while i < len(df)-1:
        row=df.iloc[i]
        if pd.isna(row["sma50"]) or pd.isna(row["vol30"]):
            i+=1; continue
        sig = row["close"]>row["sma50"] and row["volume"]>row["vol30"] and row["close"]>df["close"].iloc[i-mom_days]
        if not sig:
            i+=1; continue
        entry=df["open"].iloc[i+1]*(1+SLIP)
        stop=row["sma50"]
        if entry-stop<=0:
            i+=1; continue
        target=entry+target_r*(entry-stop)
        risk=entry-stop
        shares=int((0.01*equity)//risk//100*100)
        if shares<=0:
            i+=1; continue
        cost=entry*shares
        buy_fee=max(cost*COMMISSION,5)+cost*TRANSFER
        exit_price=None; reason="hold_expired"; exit_day=min(i+1+max_hold-1, len(df)-1)
        for j in range(i+2, min(i+1+max_hold, len(df))+1):
            if j>=len(df): break
            if df["low"].iloc[j]<=stop:
                exit_price,reason,exit_day=stop*(1-SLIP),"stop",j; break
            if df["high"].iloc[j]>=target:
                exit_price,reason,exit_day=target*(1-SLIP),"target",j; break
        if exit_price is None:
            exit_price=df["close"].iloc[exit_day]*(1-SLIP)
        proceeds=exit_price*shares
        sell_fee=max(proceeds*COMMISSION,5)+proceeds*TRANSFER+proceeds*STAMP
        pnl=proceeds-cost-buy_fee-sell_fee
        equity+=pnl; peak=max(peak,equity); max_dd=max(max_dd,(peak-equity)/peak)
        trades.append({"entry_date":str(df["date"].iloc[i+1].date()),"exit_date":str(df["date"].iloc[exit_day].date()),
                       "entry":round(entry,2),"stop":round(stop,2),"target":round(target,2),
                       "exit":round(exit_price,2),"shares":shares,"pnl":round(pnl,2),"reason":reason})
        i=exit_day+1
    return trades,equity,max_dd

def report(trades,equity,max_dd):
    t=pd.DataFrame(trades)
    if t.empty: return {"trades":0,"note":"无交易"}
    wins=t[t.pnl>0]; losses=t[t.pnl<=0]
    last=t[pd.to_datetime(t.exit_date)>=pd.to_datetime(t.exit_date).max()-pd.Timedelta(days=365)]
    return {"trades":int(len(t)),"win_rate":round(len(wins)/len(t),4),
            "avg_win":round(wins.pnl.mean(),2) if len(wins) else 0.0,
            "avg_loss":round(losses.pnl.mean(),2) if len(losses) else 0.0,
            "total_pnl":round(t.pnl.sum(),2),"final_equity":round(equity,2),
            "max_drawdown":round(max_dd,4),
            "last_year_trades":int(len(last)),"last_year_pnl":round(last.pnl.sum(),2) if len(last) else 0.0,
            "last_year_win_rate":round((last.pnl>0).mean(),4) if len(last) else 0.0,
            "reject":bool(len(t)<30 or (len(last) and last.pnl.sum()<=0)),
            "reject_reason":("交易次数少于 30 次" if len(t)<30 else "最近一年不赚钱" if len(last) and last.pnl.sum()<=0 else "")}

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("--csv",required=True); ap.add_argument("--out",default="")
    ap.add_argument("--target_r",type=float,default=2.0); ap.add_argument("--vol_window",type=int,default=30); ap.add_argument("--mom_days",type=int,default=5)
    a=ap.parse_args()
    df=load(a.csv)
    trades,equity,max_dd=run(df,target_r=a.target_r,vol_window=a.vol_window,mom_days=a.mom_days)
    r=report(trades,equity,max_dd)
    r["data_range"]=f"{df['date'].iloc[0].date()} 至 {df['date'].iloc[-1].date()}，{len(df)} 个交易日"
    r["costs"]={"commission":COMMISSION,"stamp_duty_sell":STAMP,"transfer_fee":TRANSFER,"slippage_per_side":SLIP}
    r["params"]={"target_r":a.target_r,"vol_window":a.vol_window,"mom_days":a.mom_days,"stop":"SMA50","entry":"信号次日开盘"}
    print(json.dumps(r,ensure_ascii=False,indent=2))
    if a.out:
        with open(a.out,"w",encoding="utf-8") as f: json.dump({"report":r,"trades":trades},f,ensure_ascii=False,indent=2)
