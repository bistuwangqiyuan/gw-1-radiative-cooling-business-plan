# -*- coding: utf-8 -*-
"""
GW-1 零碳辐射制冷涂料 · OEM 轻资产财务模型（可复现）
================================================================
本脚本重建《GW-1 可行性研究报告 v2.0 OEM 模式升级版》中的核心财务与
风险模型，并输出 assets/data/model_output.json 供前端商业计划书页面读取。

设计原则（实事求是 / 可复现）：
1. 所有公式与假设均显式写出，与可研报告第 6/9/12 章一一对应；
2. 蒙特卡洛使用固定随机种子，保证任何人重跑得到同一结果；
3. 重算值与报告披露值如有偏差，在控制台打印对账表并在 README 说明。

运行：
    python models/financial_model.py
依赖：numpy（见 requirements.txt）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List

import numpy as np

# --------------------------------------------------------------------------
# 0. 路径
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT_PATH = os.path.join(ROOT, "assets", "data", "model_output.json")

YEARS = [2026, 2027, 2028, 2029, 2030]


# --------------------------------------------------------------------------
# 1. 关键假设（OEM 模式，对应报告 6.1 节）
# --------------------------------------------------------------------------
@dataclass
class Assumptions:
    # 营业收入路径（亿元）
    revenue_base: List[float] = field(
        default_factory=lambda: [0.30, 2.80, 6.78, 10.24, 9.00]
    )
    revenue_aggr: List[float] = field(
        default_factory=lambda: [0.50, 3.50, 8.50, 14.00, 18.00]
    )
    cogs_ratio: float = 0.50          # 营业成本率（含 OEM 加工费 + 原料 + 包装物流 + QC）
    sga_ratio: float = 0.16           # 销售管理费用率
    rd_ratio: float = 0.09            # 研发费用率
    capex: List[float] = field(
        default_factory=lambda: [0.30, 0.20, 0.15, 0.10, 0.05]  # 合计 0.80 亿
    )
    depreciation: List[float] = field(
        default_factory=lambda: [0.06, 0.10, 0.13, 0.15, 0.16]  # 5 年折旧（设备更轻）
    )
    wc_ratio: float = 0.25            # 营运资本占收入比（OEM 预付款 + 中间品库存）
    tax_rate: float = 0.15            # 高新技术企业所得税率
    wacc: float = 0.10               # 折现率（CAPM: Rf2.5% + β1.2 × ERP6.5% + 0.5%）
    perp_growth: float = 0.03         # 永续增长率
    initial_equity: float = 1.00      # t0 初始股权投入（亿元），作为 NPV/IRR 的期初现金流出

    # 估值倍数（轻资产溢价，对应报告 12.1 节）
    pe_multiple: float = 25.0
    ps_multiple: float = 6.0


A = Assumptions()


# --------------------------------------------------------------------------
# 2. 损益表 + 现金流 + 估值（确定性模型）
# --------------------------------------------------------------------------
def build_pnl(revenue: List[float], a: Assumptions = A) -> dict:
    """构建 5 年损益表（单位：亿元）。"""
    rev = np.array(revenue, dtype=float)
    cogs = rev * a.cogs_ratio
    gross = rev - cogs
    sga = rev * a.sga_ratio
    rd = rev * a.rd_ratio
    dep = np.array(a.depreciation, dtype=float)
    ebit = gross - sga - rd - dep
    tax = np.maximum(ebit, 0) * a.tax_rate          # 亏损不计税
    net_income = ebit - tax
    return {
        "years": YEARS,
        "revenue": rev.tolist(),
        "cogs": cogs.tolist(),
        "gross": gross.tolist(),
        "sga": sga.tolist(),
        "rd": rd.tolist(),
        "depreciation": dep.tolist(),
        "ebit": ebit.tolist(),
        "tax": tax.tolist(),
        "net_income": net_income.tolist(),
    }


def build_cashflow(pnl: dict, revenue: List[float], a: Assumptions = A) -> dict:
    """构建现金流量表并计算自由现金流（FCF）。"""
    rev = np.array(revenue, dtype=float)
    ni = np.array(pnl["net_income"], dtype=float)
    dep = np.array(pnl["depreciation"], dtype=float)
    capex = np.array(a.capex, dtype=float)

    # 营运资本：占收入 wc_ratio；变动为当年与上年的差（首年与 0 比较）
    wc = rev * a.wc_ratio
    wc_prev = np.concatenate(([0.0], wc[:-1]))
    wc_change = wc - wc_prev                          # 正值=占用现金
    ocf = ni + dep - wc_change                        # 经营性现金流
    fcf = ocf - capex                                 # 自由现金流
    cum_fcf = np.cumsum(fcf)
    return {
        "net_income": ni.tolist(),
        "depreciation": dep.tolist(),
        "wc_change": (-wc_change).tolist(),           # 以现金流口径展示（负=流出）
        "ocf": ocf.tolist(),
        "capex": (-capex).tolist(),
        "fcf": fcf.tolist(),
        "cum_fcf": cum_fcf.tolist(),
    }


def terminal_value(fcf_last: float, a: Assumptions = A) -> float:
    """Gordon 永续增长终值（基于末年 FCF）。"""
    return fcf_last * (1 + a.perp_growth) / (a.wacc - a.perp_growth)


def npv_irr(fcf: List[float], tv: float, a: Assumptions = A):
    """
    计算 NPV 与 IRR。
    现金流序列：t0 = -初始股权；t1..t5 = FCF；t5 额外加终值 TV。
    """
    fcf = np.array(fcf, dtype=float)
    flows = [-a.initial_equity]                       # t0
    flows.extend(fcf.tolist())                        # t1..t5
    flows[-1] += tv                                   # 末年并入终值
    flows = np.array(flows, dtype=float)

    # NPV @ WACC
    disc = np.array([(1 + a.wacc) ** t for t in range(len(flows))])
    npv = float(np.sum(flows / disc))

    # IRR：在 [-0.99, 10] 上二分求根
    def npv_at(r):
        d = np.array([(1 + r) ** t for t in range(len(flows))])
        return np.sum(flows / d)

    lo, hi = -0.9, 10.0
    f_lo, f_hi = npv_at(lo), npv_at(hi)
    irr = None
    if f_lo * f_hi < 0:
        for _ in range(200):
            mid = (lo + hi) / 2
            f_mid = npv_at(mid)
            if abs(f_mid) < 1e-9:
                break
            if f_lo * f_mid < 0:
                hi, f_hi = mid, f_mid
            else:
                lo, f_lo = mid, f_mid
        irr = (lo + hi) / 2
    return npv, (irr if irr is not None else float("nan"))


def payback_period(cum_fcf: List[float]) -> int:
    """静态回收期（首个累计 FCF 转正的年序，从 1 计）。"""
    for i, v in enumerate(cum_fcf):
        if v >= 0:
            return i + 1
    return len(cum_fcf)


def valuation(pnl: dict, npv: float, tv: float, a: Assumptions = A) -> dict:
    """Y5 估值三法交叉验证（对应报告 12.2 节）。"""
    y5_ni = pnl["net_income"][-1]
    y5_rev = pnl["revenue"][-1]
    pe_val = y5_ni * a.pe_multiple
    ps_val = y5_rev * a.ps_multiple
    # DCF 企业价值（PV(FCF)+PV(TV)，即不扣初始股权的现值），作为交叉参考
    dcf_ev = npv + a.initial_equity
    blended = (pe_val + ps_val) / 2                   # 报告综合口径：PE 法与 PS 法均值
    return {
        "pe": round(pe_val, 2),
        "ps": round(ps_val, 2),
        "dcf_ev": round(dcf_ev, 2),
        "blended": round(blended, 2),
    }


def roic(pnl: dict, a: Assumptions = A) -> float:
    """
    投入资本回报率（口径：末年 NOPAT / 投入资本）。
    投入资本 = 累计 CAPEX + 末年净营运资本（轻资产口径）。
    """
    y5_ebit = pnl["ebit"][-1]
    nopat = y5_ebit * (1 - a.tax_rate)
    invested = sum(a.capex) + pnl["revenue"][-1] * a.wc_ratio
    return float(nopat / invested)


def run_deterministic(revenue: List[float], a: Assumptions = A) -> dict:
    pnl = build_pnl(revenue, a)
    cf = build_cashflow(pnl, revenue, a)
    tv = terminal_value(cf["fcf"][-1], a)
    npv, irr = npv_irr(cf["fcf"], tv, a)
    val = valuation(pnl, npv, tv, a)
    return {
        "pnl": pnl,
        "cashflow": cf,
        "tv": round(tv, 2),
        "npv": round(npv, 2),
        "irr": round(irr * 100, 1),
        "payback": payback_period(cf["cum_fcf"]),
        "roic": round(roic(pnl, a) * 100, 1),
        "cum_ni": round(sum(pnl["net_income"]), 2),
        "cum_capex": round(sum(a.capex), 2),
        "valuation": val,
    }


# --------------------------------------------------------------------------
# 3. 蒙特卡洛仿真（对应报告第 9 章，50,000 次）
# --------------------------------------------------------------------------
N_SIM = 50_000
SEED = 20260607


def _tri(rng, lo, mode, hi, n):
    return rng.triangular(lo, mode, hi, n)


def monte_carlo(a: Assumptions = A, n: int = N_SIM, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    base_rev = np.array(a.revenue_base, dtype=float)
    dep = np.array(a.depreciation, dtype=float)
    base_capex = np.array(a.capex, dtype=float)

    # 11 个关键变量分布（报告 9.2 节）
    rev_mult = _tri(rng, 0.55, 1.00, 1.45, n)
    cogs = _tri(rng, 0.45, 0.50, 0.58, n)
    oem_fee = _tri(rng, 0.85, 1.00, 1.20, n)          # OEM 加工费乘数（作用于 COGS 中约 12% 的加工费部分）
    sga = _tri(rng, 0.13, 0.16, 0.20, n)
    rd = _tri(rng, 0.07, 0.09, 0.12, n)
    tax = _tri(rng, 0.10, 0.15, 0.25, n)
    wacc = _tri(rng, 0.07, 0.10, 0.14, n)
    capex_mult = _tri(rng, 0.80, 1.00, 1.40, n)
    wc = _tri(rng, 0.18, 0.25, 0.32, n)
    # 推广延迟（年）：按报告 R8 权威分布 50%/30%/20%（0/1/2 年）
    delay = rng.choice([0, 1, 2], size=n, p=[0.50, 0.30, 0.20])
    quality_hit = (rng.random(n) < 0.05).astype(int)  # 5% 概率重大质量事故

    npvs = np.empty(n)
    irrs = np.empty(n)
    vals = np.empty(n)

    # OEM 加工费占收入的基准比例（用于让 oem_fee 乘数有独立作用）
    oem_fee_base = 0.12

    for i in range(n):
        # 推广延迟：收入路径整体后移 delay 年（前移补 0）
        d = int(delay[i])
        rev = np.zeros(5)
        if d == 0:
            rev = base_rev.copy()
        else:
            rev[d:] = base_rev[: 5 - d]

        rev = rev * rev_mult[i]

        # 质量事故：随机命中某一已放量年份，当年收入 -30%，
        # 并按报告 8.3 节"品牌损失 1-2 年"对次年额外 -15%
        if quality_hit[i]:
            hit_year = rng.integers(2, 5)             # 命中 2028/2029/2030 之一
            rev[hit_year] *= 0.70
            if hit_year + 1 < 5:
                rev[hit_year + 1] *= 0.85

        # 成本：基础 COGS 比例 + OEM 加工费乘数对加工费部分的调整
        eff_cogs = cogs[i] + oem_fee_base * (oem_fee[i] - 1.0)
        cogs_amt = rev * eff_cogs
        gross = rev - cogs_amt
        ebit = gross - rev * sga[i] - rev * rd[i] - dep
        tax_amt = np.maximum(ebit, 0) * tax[i]
        ni = ebit - tax_amt
        # 质量事故罚款 0.3 亿计入命中年净利
        if quality_hit[i]:
            ni[hit_year] -= 0.30

        wc_arr = rev * wc[i]
        wc_prev = np.concatenate(([0.0], wc_arr[:-1]))
        ocf = ni + dep - (wc_arr - wc_prev)
        fcf = ocf - base_capex * capex_mult[i]

        tv = fcf[-1] * (1 + a.perp_growth) / (wacc[i] - a.perp_growth)
        if tv < 0:
            tv = 0.0

        flows = np.concatenate(([-a.initial_equity], fcf))
        flows[-1] += tv
        disc = np.array([(1 + wacc[i]) ** t for t in range(len(flows))])
        npv = float(np.sum(flows / disc))
        npvs[i] = npv

        # 简化 IRR：用 NPV>0 与近似法（对统计分布足够）
        # 采用与确定性一致的二分，但为性能用粗粒度
        irrs[i] = _quick_irr(flows)

        # Y5 估值（PE 与 PS 均值）
        vals[i] = (ni[-1] * a.pe_multiple + rev[-1] * a.ps_multiple) / 2

    # 概率指标
    p_success = float(np.mean(npvs > 0) * 100)
    p_strong = float(np.mean((npvs > 10) & (irrs > 0.30)) * 100)
    p_excellent = float(np.mean((npvs > 30) & (irrs > 0.50)) * 100)
    p_fail = float(np.mean(npvs < 0) * 100)
    p_bankrupt = float(np.mean(npvs < -1) * 100)

    # 直方图（用于前端分布图）
    hist_counts, hist_edges = np.histogram(npvs, bins=40, range=(-10, 40))

    # 风险贡献度（Pearson 相关 + 解释方差占比）
    drivers = {
        "delay": delay.astype(float),
        "wacc": wacc,
        "oem_fee": oem_fee,
        "rev_mult": rev_mult,
        "cogs": cogs,
        "quality_hit": quality_hit.astype(float),
        "sga": sga,
        "rd": rd,
    }
    contrib = []
    pearsons = {}
    for k, v in drivers.items():
        r = float(np.corrcoef(v, npvs)[0, 1])
        pearsons[k] = r
    total_r2 = sum(r * r for r in pearsons.values())
    for k, r in pearsons.items():
        contrib.append({
            "var": k,
            "pearson": round(r, 4),
            "variance_pct": round((r * r / total_r2) * 100, 2),
        })
    contrib.sort(key=lambda x: x["variance_pct"], reverse=True)

    return {
        "n_sim": n,
        "seed": seed,
        "npv_mean": round(float(np.mean(npvs)), 2),
        "npv_median": round(float(np.median(npvs)), 2),
        "npv_p5": round(float(np.percentile(npvs, 5)), 2),
        "npv_p95": round(float(np.percentile(npvs, 95)), 2),
        "irr_mean": round(float(np.nanmean(irrs)) * 100, 1),
        "val_mean": round(float(np.mean(vals)), 2),
        "val_p5": round(float(np.percentile(vals, 5)), 2),
        "val_p95": round(float(np.percentile(vals, 95)), 2),
        "p_success": round(p_success, 2),
        "p_strong": round(p_strong, 2),
        "p_excellent": round(p_excellent, 2),
        "p_fail": round(p_fail, 2),
        "p_bankrupt": round(p_bankrupt, 2),
        "hist_counts": hist_counts.tolist(),
        "hist_edges": [round(x, 2) for x in hist_edges.tolist()],
        "risk_contribution": contrib,
    }


def _quick_irr(flows: np.ndarray) -> float:
    """二分法 IRR（容差较宽，用于 MC 统计）。"""
    def f(r):
        d = np.array([(1 + r) ** t for t in range(len(flows))])
        return np.sum(flows / d)
    lo, hi = -0.9, 10.0
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return float("nan")
    for _ in range(80):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


# --------------------------------------------------------------------------
# 4. 单变量敏感性（龙卷风图，对应报告 9.5 节）
# --------------------------------------------------------------------------
def sensitivity(a: Assumptions = A) -> List[dict]:
    base = run_deterministic(a.revenue_base, a)
    base_npv = base["npv"]
    out = []

    def npv_with(**kw):
        aa = Assumptions(**{**a.__dict__, **kw})
        return run_deterministic(aa.revenue_base, aa)["npv"]

    # 各因子 ±10%
    factors = {
        "营业收入": lambda s: run_deterministic([r * (1 + s) for r in a.revenue_base], a)["npv"],
        "OEM加工费/原料(COGS)": lambda s: npv_with(cogs_ratio=a.cogs_ratio * (1 + s)),
        "折现率(WACC)": lambda s: npv_with(wacc=a.wacc * (1 + s)),
        "销售管理费率(SG&A)": lambda s: npv_with(sga_ratio=a.sga_ratio * (1 + s)),
        "研发费率(R&D)": lambda s: npv_with(rd_ratio=a.rd_ratio * (1 + s)),
        "所得税率": lambda s: npv_with(tax_rate=a.tax_rate * (1 + s)),
        "营运资本占比": lambda s: npv_with(wc_ratio=a.wc_ratio * (1 + s)),
        "CAPEX": lambda s: npv_with(capex=[c * (1 + s) for c in a.capex]),
    }
    for name, fn in factors.items():
        low = fn(-0.10)
        high = fn(0.10)
        out.append({
            "factor": name,
            "low": round(low, 2),
            "high": round(high, 2),
            "swing": round(abs(high - low), 2),
        })
    out.sort(key=lambda x: x["swing"], reverse=True)
    return out, base_npv


# --------------------------------------------------------------------------
# 5. 自建 vs OEM 对比（自建为 v1.0 报告披露值，OEM 为本模型重算值）
# --------------------------------------------------------------------------
def comparison_table(oem: dict) -> dict:
    return {
        "dimensions": [
            "5年累计CAPEX", "初始股权融资", "COGS比率", "SG&A比率",
            "研发费率", "营运资本占比", "折旧周期", "NPV(亿元)",
            "IRR(%)", "静态回收期", "ROIC(%)", "Y5市值(亿元)",
        ],
        "self_built": {  # v1.0 报告披露值
            "CAPEX": 3.10, "equity": 2.0, "cogs": 42, "sga": 18, "rd": 8,
            "wc": 20, "dep_years": 8, "npv": 23.08, "irr": 73.7,
            "payback": 5, "roic": 26.1, "valuation": 36.94,
        },
        "oem": {  # 本模型重算值
            "CAPEX": oem["cum_capex"], "equity": 1.0, "cogs": 50, "sga": 16, "rd": 9,
            "wc": 25, "dep_years": 5, "npv": oem["npv"], "irr": oem["irr"],
            "payback": oem["payback"], "roic": oem["roic"],
            "valuation": oem["valuation"]["blended"],
        },
    }


# --------------------------------------------------------------------------
# 6. 市场与融资（来自报告第 3 / 11 章）
# --------------------------------------------------------------------------
def market_and_funding() -> dict:
    return {
        "sam_m2": 7.34,                               # 亿 m²/年
        "penetration_base": 0.34,                     # %
        "penetration_aggr": 0.61,                     # %
        "revenue_base": A.revenue_base,
        "revenue_aggr": A.revenue_aggr,
        "funding_rounds": [
            {"round": "种子", "time": "2026 Q1", "amount": 0.20, "premoney": 0.5, "dilution": 30,
             "milestone": "MVP + 中试线 + 首批 OEM 试制"},
            {"round": "Pre-A", "time": "2026 Q4", "amount": 0.50, "premoney": 1.5, "dilution": 25,
             "milestone": "首个 KA Demo + OEM 量产 + 第 1 张大单"},
            {"round": "A 轮", "time": "2027 Q4", "amount": 1.50, "premoney": 4.0, "dilution": 22,
             "milestone": "5+ KA 客户 + 多 SKU 量产 + 出海首站"},
            {"round": "B 轮", "time": "2029 Q1", "amount": 4.00, "premoney": 12.0, "dilution": 25,
             "milestone": "规模化 + IPO Pre 准备"},
            {"round": "IPO", "time": "2030", "amount": 8.00, "premoney": 50.0, "dilution": 16,
             "milestone": "A 股科创板第 5 套标准 / 港股 18C"},
        ],
        # A 轮 1.5 亿资金用途拆解（基于报告战略：研发/销售网络/品牌/现金储备）
        "use_of_funds_A": [
            {"item": "应用工程与配方研发", "pct": 30, "amount": 0.45},
            {"item": "销售网络与 KA 拓展", "pct": 30, "amount": 0.45},
            {"item": "品牌建设与 ESG 叙事", "pct": 15, "amount": 0.225},
            {"item": "OEM 战略保供与备份", "pct": 13, "amount": 0.195},
            {"item": "营运资本与现金储备", "pct": 12, "amount": 0.18},
        ],
    }


# --------------------------------------------------------------------------
# 7. 主程序
# --------------------------------------------------------------------------
def main():
    print("=" * 64)
    print("GW-1 OEM 财务模型 · 重算与对账")
    print("=" * 64)

    oem_base = run_deterministic(A.revenue_base)
    oem_aggr = run_deterministic(A.revenue_aggr)

    print("\n[基线情景] 损益表净利润(亿):", [round(x, 2) for x in oem_base["pnl"]["net_income"]])
    print("[基线情景] 自由现金流(亿):", [round(x, 2) for x in oem_base["cashflow"]["fcf"]])

    print("\n--- 关键指标对账（重算值 vs 报告披露值）---")
    rows = [
        ("NPV(亿元)", oem_base["npv"], 21.06),
        ("IRR(%)", oem_base["irr"], 99.7),
        ("终值TV(亿元)", oem_base["tv"], 32.32),
        ("回收期(年)", oem_base["payback"], 4),
        ("累计净利(亿元)", oem_base["cum_ni"], 5.68),
        ("Y5估值-PE法(亿)", oem_base["valuation"]["pe"], 44.41),
        ("Y5估值-PS法(亿)", oem_base["valuation"]["ps"], 54.00),
        ("Y5估值-综合(亿)", oem_base["valuation"]["blended"], 49.21),
        ("ROIC(%)", oem_base["roic"], 63.1),
    ]
    print(f"{'指标':<20}{'重算值':>12}{'报告值':>12}{'差异':>12}")
    for name, calc, rep in rows:
        diff = round(calc - rep, 2)
        print(f"{name:<20}{calc:>12}{rep:>12}{diff:>12}")

    print("\n--- 蒙特卡洛仿真（%d 次，种子 %d）---" % (N_SIM, SEED))
    mc = monte_carlo()
    mc_rows = [
        ("P(NPV>0) 成功率%", mc["p_success"], 91.87),
        ("P(强成功)%", mc["p_strong"], 58.33),
        ("P(卓越)%", mc["p_excellent"], 4.33),
        ("P(失败)%", mc["p_fail"], 8.13),
        ("P(破产)%", mc["p_bankrupt"], 5.51),
        ("NPV均值(亿)", mc["npv_mean"], 12.61),
        ("NPV中位(亿)", mc["npv_median"], 11.97),
        ("NPV_P5(亿)", mc["npv_p5"], -1.25),
        ("NPV_P95(亿)", mc["npv_p95"], 29.19),
        ("Y5估值均值(亿)", mc["val_mean"], 45.49),
    ]
    print(f"{'指标':<20}{'重算值':>12}{'报告值':>12}{'差异':>12}")
    for name, calc, rep in mc_rows:
        diff = round(calc - rep, 2)
        print(f"{name:<20}{calc:>12}{rep:>12}{diff:>12}")

    sens, base_npv = sensitivity()
    comp = comparison_table(oem_base)
    mkt = market_and_funding()

    output = {
        "meta": {
            "project": "GW-1 零碳辐射制冷涂料",
            "model": "OEM 轻资产财务模型 v2.0",
            "seed": SEED,
            "n_sim": N_SIM,
            "assumptions": {
                "cogs_ratio": A.cogs_ratio, "sga_ratio": A.sga_ratio,
                "rd_ratio": A.rd_ratio, "wc_ratio": A.wc_ratio,
                "tax_rate": A.tax_rate, "wacc": A.wacc,
                "perp_growth": A.perp_growth, "initial_equity": A.initial_equity,
                "pe_multiple": A.pe_multiple, "ps_multiple": A.ps_multiple,
                "capex_total": round(sum(A.capex), 2),
            },
        },
        "oem_base": oem_base,
        "oem_aggr": oem_aggr,
        "montecarlo": mc,
        "sensitivity": sens,
        "comparison": comp,
        "market": mkt,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\n[OK] 已写出:", OUT_PATH)

    # 同时输出 JS 版本（挂载到 window.MODEL_DATA），便于前端以 file:// 直接打开
    js_path = os.path.join(os.path.dirname(OUT_PATH), "model_data.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("/* 由 models/financial_model.py 自动生成，请勿手改。*/\n")
        f.write("window.MODEL_DATA = ")
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    print("[OK] 已写出:", js_path)


if __name__ == "__main__":
    main()
