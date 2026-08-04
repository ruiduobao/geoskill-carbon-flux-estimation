#!/usr/bin/env python3
"""carbon-flux-estimation — 碳通量估算（光能利用率模型）

用简化的光能利用率模型（CASA / VPM 思路）估算生态系统碳通量：

- **GPP**（总初级生产力）= PAR × FPAR × ε
  - PAR：光合有效辐射（MJ/m²/day）
  - FPAR：光合有效辐射吸收比例（0-1）
  - ε：实际光能利用率 = εmax × Tstress × Wstress（gC/MJ）
- **温度胁迫** Tstress：以 Topt 为最适温度的抛物线响应，低温/高温均降低。
- **水分胁迫** Wstress：随可用水分量（0-1）线性/非线性调节。
- **自养呼吸** Ra = GPP × ra_frac(T)（温度升高呼吸占比增大）。
- **NPP**（净初级生产力）= GPP − Ra。

量级校准：εmax≈0.4 gC/MJ、PAR≈20-40 MJ/m²/day、FPAR≈0.3-0.85，得到日 GPP
约 2-12 gC/m²/day，年累计落在植被合理范围（数百至上千 gC/m²/yr）。

数据源：本地多波段 GeoTIFF（PAR/FPAR/温度/水分），或 ``--synthetic`` 生成
物理一致的栅格与时序（离线）。

隐私声明 / Privacy：默认离线，``--synthetic`` 完全无网络，所有处理本地完成。

Usage:
    python carbon-flux-estimation.py --bbox 116 39 117 40 --output-dir ./out
    python carbon-flux-estimation.py --bbox 116 39 117 40 --synthetic --n-dates 30 --output-dir ./out
    python carbon-flux-estimation.py --input par_fpar_temp.tif --output-dir ./out

License: MIT
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

VERSION = "1.0.0"
SKILL_NAME = "carbon-flux-estimation"

try:
    from _geoskill_core.errors import (
        GeoSkillError, UsageError, ValidationError, ProcessError, to_exit_code,
    )
    from _geoskill_core.manifest import OutputManifest, OutputFile
except ImportError:  # pragma: no cover
    class GeoSkillError(Exception):
        def __init__(self, message: str, code: int = 7, kind: str = "EGeo", **kw):
            super().__init__(message)
            self.message, self.code, self.kind = message, code, kind

    class UsageError(GeoSkillError):
        def __init__(self, m, **k): super().__init__(m, code=2, kind="EUsage", **k)

    class ValidationError(GeoSkillError):
        def __init__(self, m, **k): super().__init__(m, code=6, kind="EValidate", **k)

    class ProcessError(GeoSkillError):
        def __init__(self, m, **k): super().__init__(m, code=7, kind="EProcess", **k)

    def to_exit_code(exc):
        return getattr(exc, "code", 7)

    OutputManifest = None
    OutputFile = None


# 模型参数
EPS_MAX = 0.40        # 最大光能利用率 (gC/MJ)
T_OPT = 25.0          # 最适温度 (°C)
T_MIN = 0.0           # 光合下限温度 (°C)
T_MAX = 45.0          # 光合上限温度 (°C)
RA_FRAC_BASE = 0.45   # 基础自养呼吸占比（20°C 参考温度）
RA_TEMP_COEF = 0.010  # 呼吸占比随温度升高的增量 (/°C)
RA_FRAC_MIN = 0.30    # 呼吸占比下限
RA_FRAC_MAX = 0.80    # 呼吸占比上限


def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def validate_bbox(bbox, ctx: str = "bbox") -> None:
    """Validate a (W, S, E, N) bbox: 4 floats, lon/lat ranges, W<E, S<N.

    Antimeridian crossing (W > E) is NOT supported; raises ValidationError
    suggesting the user split the bbox.
    """
    if bbox is None or len(bbox) != 4:
        raise UsageError(f"{ctx}: expected 4 floats (W S E N); got {bbox!r}")
    try:
        w, s, e, n = [float(v) for v in bbox]
    except (TypeError, ValueError):
        raise UsageError(f"{ctx}: bbox values must be numeric; got {bbox!r}")
    if not (all(np.isfinite([w, s, e, n]))):
        raise ValidationError(f"{ctx}: bbox values must be finite; got {bbox!r}")
    if not (-180.0 <= w <= 180.0 and -180.0 <= e <= 180.0):
        raise ValidationError(
            f"{ctx}: longitude out of range (got W={w} E={e}); expected -180..180"
        )
    if not (-90.0 <= s <= 90.0 and -90.0 <= n <= 90.0):
        raise ValidationError(
            f"{ctx}: latitude out of range (got S={s} N={n}); expected -90..90"
        )
    if w >= e:
        raise ValidationError(
            f"{ctx}: requires W < E (got W={w} E={e}); "
            f"antimeridian crossing is not supported — split the bbox into two."
        )
    if s >= n:
        raise ValidationError(f"{ctx}: requires S < N (got S={s} N={n})")
    if (e - w) < 1e-6 or (n - s) < 1e-6:
        raise ValidationError(
            f"{ctx}: bbox extent too small ({(e - w):.2e} x {(n - s):.2e} deg); "
            f"need at least ~1e-6 deg in each direction"
        )


# ---------------------------------------------------------------------------
# 核心算法
# ---------------------------------------------------------------------------
def temperature_stress(temp: np.ndarray, t_opt: float = T_OPT,
                       t_min: float = T_MIN, t_max: float = T_MAX) -> np.ndarray:
    """温度胁迫因子（0-1），在 t_opt 处为 1，低于 t_min 或高于 t_max 为 0。

    用最适温度两侧拼接的抛物线：
    - T <= t_opt: f = 1 - ((t_opt - T)/(t_opt - t_min))²
    - T >  t_opt: f = 1 - ((T - t_opt)/(t_max - t_opt))²
    """
    t = np.asarray(temp, dtype=np.float64)
    low = 1.0 - ((t_opt - t) / (t_opt - t_min)) ** 2
    high = 1.0 - ((t - t_opt) / (t_max - t_opt)) ** 2
    f = np.where(t <= t_opt, low, high)
    return np.clip(f, 0.0, 1.0)


def water_stress(water: np.ndarray) -> np.ndarray:
    """水分胁迫因子（0-1）：可用水分量经非线性调节。"""
    w = np.clip(np.asarray(water, dtype=np.float64), 0.0, 1.0)
    # 轻度干旱即开始受限，湿润区接近 1
    return np.clip(0.5 + 0.5 * np.sin(np.pi * (w - 0.5)), 0.0, 1.0)


def actual_efficiency(temp: np.ndarray, water: np.ndarray,
                      eps_max: float = EPS_MAX) -> np.ndarray:
    """实际光能利用率 ε = εmax × Tstress × Wstress (gC/MJ)。"""
    return eps_max * temperature_stress(temp) * water_stress(water)


def gpp(par: np.ndarray, fpar: np.ndarray, temp: np.ndarray,
        water: np.ndarray, eps_max: float = EPS_MAX) -> np.ndarray:
    """总初级生产力 GPP = PAR × FPAR × ε (gC/m²/day)。"""
    fpar_c = np.clip(np.asarray(fpar, dtype=np.float64), 0.0, 1.0)
    par_c = np.clip(np.asarray(par, dtype=np.float64), 0.0, None)
    eps = actual_efficiency(temp, water, eps_max)
    return par_c * fpar_c * eps


def autotrophic_respiration(gpp_arr: np.ndarray, temp: np.ndarray) -> np.ndarray:
    """自养呼吸 Ra = GPP × ra_frac(T)，温度越高呼吸占比越大。

    ra_frac 以 20°C 为参考锚点线性增长，裁剪到 [RA_FRAC_MIN, RA_FRAC_MAX]，
    使生长季 NPP/GPP 落在观测范围 0.45-0.55（Zhang et al. 2009）附近。
    """
    ra_frac = RA_FRAC_BASE + RA_TEMP_COEF * (
        np.asarray(temp, dtype=np.float64) - 20.0
    )
    ra_frac = np.clip(ra_frac, RA_FRAC_MIN, RA_FRAC_MAX)
    return np.asarray(gpp_arr, dtype=np.float64) * ra_frac


def npp(par: np.ndarray, fpar: np.ndarray, temp: np.ndarray,
        water: np.ndarray, eps_max: float = EPS_MAX) -> Tuple[np.ndarray, np.ndarray]:
    """返回 (GPP, NPP)，NPP = GPP − Ra。"""
    g = gpp(par, fpar, temp, water, eps_max)
    ra = autotrophic_respiration(g, temp)
    return g, g - ra


def compute_flux_series(par: np.ndarray, fpar: np.ndarray, temp: np.ndarray,
                        water: np.ndarray) -> Dict[str, np.ndarray]:
    """逐日计算 GPP/Ra/NPP。输入 (n,H,W)，返回同名键数组。"""
    par = np.asarray(par, dtype=np.float64)
    if not (par.shape == fpar.shape == temp.shape == water.shape):
        raise ValidationError(
            f"flux arrays shape mismatch: {par.shape} {fpar.shape} {temp.shape} {water.shape}")
    if par.ndim != 3:
        raise ValidationError(f"flux arrays must be 3D (n,H,W), got ndim={par.ndim}")
    n = par.shape[0]
    GPP = np.zeros_like(par, dtype=np.float32)
    RA = np.zeros_like(par, dtype=np.float32)
    NPP = np.zeros_like(par, dtype=np.float32)
    for t in range(n):
        g, nv = npp(par[t], fpar[t], temp[t], water[t])
        GPP[t] = g.astype(np.float32)
        NPP[t] = nv.astype(np.float32)
        RA[t] = (g - nv).astype(np.float32)
    return {"GPP": GPP, "Ra": RA, "NPP": NPP}


# ---------------------------------------------------------------------------
# 合成数据：PAR/FPAR/温度/水分栅格与时序（离线）
# ---------------------------------------------------------------------------
def generate_synthetic(bbox: List[float], n_dates: int = 30,
                       width: int = 64, height: int = 64,
                       seed: int = 42) -> Dict[str, Any]:
    """生成物理一致的 PAR/FPAR/温度/水分场。

    空间上植被（高 FPAR）与裸地/水（低 FPAR）分区；温度带南北梯度；
    水分东湿西干。返回数组均为 (n_dates, H, W)。
    """
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    yy = yy / max(height - 1, 1)
    xx = xx / max(width - 1, 1)

    # FPAR 空间基底：右上植被茂密，左下偏裸地/水
    fpar_base = np.clip(0.2 + 0.6 * (xx + (1.0 - yy)) / 2.0, 0.05, 0.9)
    temp_base = 26.0 - 6.0 * yy          # 南暖北凉
    water_base = np.clip(0.3 + 0.5 * xx, 0.1, 0.95)  # 东湿西干

    start = _dt.datetime(2025, 6, 1)
    dates = [(start + _dt.timedelta(days=int(i))).strftime("%Y-%m-%d") for i in range(n_dates)]

    par = np.zeros((n_dates, height, width), dtype=np.float32)
    fpar = np.zeros((n_dates, height, width), dtype=np.float32)
    temp = np.zeros((n_dates, height, width), dtype=np.float32)
    water = np.zeros((n_dates, height, width), dtype=np.float32)
    for t in range(n_dates):
        # PAR 日变化：晴天高，叠加云量噪声
        cloud = rng.uniform(0.6, 1.0)
        par[t] = (35.0 * cloud + 5.0 * np.sin(2 * np.pi * xx)
                  + rng.normal(0, 1.0, (height, width)))
        fpar[t] = fpar_base + rng.normal(0, 0.02, (height, width))
        temp[t] = temp_base + rng.normal(0, 0.8, (height, width))
        water[t] = water_base + rng.normal(0, 0.03, (height, width))
        par[t] = np.clip(par[t], 1.0, None)
        fpar[t] = np.clip(fpar[t], 0.0, 1.0)
        temp[t] = np.clip(temp[t], -5.0, 48.0)
        water[t] = np.clip(water[t], 0.0, 1.0)

    info = {
        "bbox": bbox, "width": width, "height": height, "n_dates": n_dates,
        "dates": dates, "seed": seed,
    }
    return {"par": par, "fpar": fpar, "temp": temp, "water": water, "info": info}


# ---------------------------------------------------------------------------
# GeoTIFF I/O
# ---------------------------------------------------------------------------
def write_geotiff(path: str, cube: np.ndarray, bbox: List[float],
                  nodata: float = -9999.0) -> None:
    import rasterio
    from rasterio.transform import from_bounds

    if cube.ndim == 2:
        cube = cube[np.newaxis, ...]
    nb, h, w = cube.shape
    transform = from_bounds(bbox[0], bbox[1], bbox[2], bbox[3], w, h)
    profile = {
        "driver": "GTiff", "height": h, "width": w, "count": nb,
        "dtype": "float32", "crs": "EPSG:4326", "transform": transform,
        "nodata": nodata, "compress": "deflate",
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        for b in range(nb):
            band = cube[b].astype("float32")
            band = np.where(np.isfinite(band), band, nodata)
            dst.write(band, b + 1)


def read_geotiff(path: str) -> Tuple[np.ndarray, List[float]]:
    """Read multi-band GeoTIFF → (cube (nb, H, W) float32, bbox [W, S, E, N]).

    NoData values (from raster profile) are converted to NaN so the caller
    can mask them out via ``np.isfinite``.
    """
    import rasterio
    if not os.path.exists(path):
        raise UsageError(f"input raster not found: {path}", path=path)
    with rasterio.open(path) as src:
        cube = src.read().astype(np.float32)
        nodata = src.nodata
        b = src.bounds
        bbox = [b.left, b.bottom, b.right, b.top]
    if nodata is not None:
        nd = float(nodata)
        cube = np.where(cube == nd, np.nan, cube)
    return cube, bbox


def write_manifest(output_dir, args, outputs, qa, started_at, exit_code, bbox):
    if OutputManifest is None:
        return None
    cmd = " ".join([SKILL_NAME] + sys.argv[1:])
    man = OutputManifest(
        skill=SKILL_NAME, skill_version=VERSION, command=cmd,
        started_at=started_at, finished_at=_utc_now(), exit_code=exit_code,
        inputs={
            "input": getattr(args, "input", None),
            "synthetic": bool(getattr(args, "synthetic", False)),
            "n_dates": getattr(args, "n_dates", None),
        },
        outputs=[OutputFile(**o) for o in outputs], qa=qa,
        software={"python": sys.version.split()[0], "skill": SKILL_NAME},
    )
    path = os.path.join(output_dir, "output-manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(man.to_dict(), f, ensure_ascii=False, indent=2, default=str)
    return path


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def process(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    output_dir = args.output_dir
    bbox = list(args.bbox) if args.bbox else None

    synth_info: Optional[Dict[str, Any]] = None
    if args.input and not args.synthetic:
        cube, file_bbox = read_geotiff(args.input)
        bbox = bbox if bbox is not None else file_bbox
        if cube.shape[0] < 4:
            raise ValidationError(
                "input raster must have >=4 bands (PAR, FPAR, temp, water); "
                f"got {cube.shape[0]}", bands=int(cube.shape[0]))
        par = cube[0:1]; fpar = cube[1:2]; temp = cube[2:3]; water = cube[3:4]
        dates = ["single-day"]
        source_note = args.input
    else:
        if bbox is None:
            raise UsageError("provide --bbox (synthetic mode) or --input <raster>")
        met = generate_synthetic(bbox, n_dates=args.n_dates)
        par, fpar, temp, water = met["par"], met["fpar"], met["temp"], met["water"]
        synth_info = met["info"]
        dates = synth_info["dates"]
        source_note = "synthetic"

    # ---- validation (BEFORE os.makedirs to avoid empty output dirs) ----
    if bbox is None:
        raise UsageError("could not determine bbox")
    validate_bbox(bbox, ctx="bbox")
    if args.n_dates < 1:
        raise ValidationError(f"--n-dates must be >= 1 (got {args.n_dates})")
    if par.size == 0:
        raise ValidationError("input data is empty")
    if args.input and not args.synthetic:
        valid_count = int(np.sum(np.isfinite(cube)))
        if valid_count == 0:
            raise ValidationError(
                f"input raster has no valid (non-NoData) pixels: {args.input}"
            )
        # 输入值域校验（FPAR/水分 ∈ [0,1]，PAR ≥ 0，去 NoData 后检查）
        fpar_f = fpar[np.isfinite(fpar)]
        water_f = water[np.isfinite(water)]
        par_f = par[np.isfinite(par)]
        if fpar_f.size and (float(fpar_f.min()) < -0.01 or float(fpar_f.max()) > 1.01):
            raise ValidationError(
                "FPAR band (band 2) must be within [0, 1]; "
                f"got min={float(fpar_f.min())} max={float(fpar_f.max())}"
            )
        if water_f.size and (float(water_f.min()) < -0.01 or float(water_f.max()) > 1.01):
            raise ValidationError(
                "water band (band 4) must be within [0, 1]; "
                f"got min={float(water_f.min())} max={float(water_f.max())}"
            )
        if par_f.size and float(par_f.min()) < -0.01:
            raise ValidationError(
                f"PAR band (band 1) must be non-negative; got min={float(par_f.min())}"
            )
    os.makedirs(output_dir, exist_ok=True)

    series = compute_flux_series(par, fpar, temp, water)

    # 累计 GPP/NPP 栅格（时段总量）
    gpp_total = np.sum(series["GPP"], axis=0).astype(np.float32)
    npp_total = np.sum(series["NPP"], axis=0).astype(np.float32)
    flux_stack = np.stack([gpp_total, npp_total], axis=0)
    out_tif = os.path.join(output_dir, "carbon_flux.tif")
    write_geotiff(out_tif, flux_stack, bbox)

    # 时序：逐日空间均值（NaN-aware）
    timeseries = {
        "dates": dates,
        "GPP_mean": [float(np.nanmean(series["GPP"][t])) for t in range(len(dates))],
        "NPP_mean": [float(np.nanmean(series["NPP"][t])) for t in range(len(dates))],
        "Ra_mean": [float(np.nanmean(series["Ra"][t])) for t in range(len(dates))],
    }
    ts_path = os.path.join(output_dir, "flux_timeseries.json")
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(timeseries, f, ensure_ascii=False, indent=2)

    # 碳收支 JSON（NaN-aware 统计）
    mean_daily_gpp = float(np.nanmean(series["GPP"]))
    mean_daily_npp = float(np.nanmean(series["NPP"]))
    mean_daily_ra = float(np.nanmean(series["Ra"]))
    mean_total_gpp = float(np.nanmean(gpp_total))
    mean_total_npp = float(np.nanmean(npp_total))
    n_valid_pixels = int(np.sum(np.isfinite(flux_stack[0])))
    n_total_pixels = int(flux_stack[0].size)
    budget = {
        "period_days": int(len(dates)),
        "mean_daily_GPP_gC_m2": mean_daily_gpp,
        "mean_daily_NPP_gC_m2": mean_daily_npp,
        "mean_daily_Ra_gC_m2": mean_daily_ra,
        "total_GPP_gC_m2": mean_total_gpp,
        "total_NPP_gC_m2": mean_total_npp,
        "total_Ra_gC_m2": mean_total_gpp - mean_total_npp,
        "NPP_GPP_ratio": float(mean_total_npp / max(mean_total_gpp, 1e-9)),
    }
    budget_path = os.path.join(output_dir, "carbon_budget.json")
    with open(budget_path, "w", encoding="utf-8") as f:
        json.dump(budget, f, ensure_ascii=False, indent=2)

    qa: Dict[str, Any] = {
        "source": source_note,
        "n_dates": int(len(dates)),
        "n_valid_pixels": n_valid_pixels,
        "n_total_pixels": n_total_pixels,
        "mean_daily_GPP_gC_m2": budget["mean_daily_GPP_gC_m2"],
        "mean_daily_NPP_gC_m2": budget["mean_daily_NPP_gC_m2"],
        "NPP_GPP_ratio": budget["NPP_GPP_ratio"],
    }
    if args.input and not args.synthetic:
        qa["input_nodata"] = -9999.0
    outputs = [
        {"path": out_tif, "kind": "raster", "crs_epsg": 4326,
         "bbox_wgs84": bbox, "band_count": 2},
        {"path": ts_path, "kind": "json"},
        {"path": budget_path, "kind": "json"},
    ]
    man_path = write_manifest(output_dir, args, outputs, qa, started_at, 0, bbox)

    if not args.quiet:
        print(f"[{SKILL_NAME}] source: {source_note}  n_dates: {len(dates)}")
        print(f"[{SKILL_NAME}] mean daily GPP: {budget['mean_daily_GPP_gC_m2']:.3f} gC/m2/day")
        print(f"[{SKILL_NAME}] mean daily NPP: {budget['mean_daily_NPP_gC_m2']:.3f} gC/m2/day")
        print(f"[{SKILL_NAME}] NPP/GPP ratio: {budget['NPP_GPP_ratio']:.3f}")
        print(f"[{SKILL_NAME}] output: {out_tif}")
        if man_path:
            print(f"[{SKILL_NAME}] manifest: {man_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=SKILL_NAME,
        description="Carbon flux estimation (GPP/NPP) via a light-use-efficiency model (CASA/VPM simplified).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"),
                   help="geographic extent [minLon minLat maxLon maxLat]")
    p.add_argument("--input", help="input GeoTIFF (4 bands: PAR, FPAR, temp, water)")
    p.add_argument("--n-dates", type=int, default=30,
                   help="number of synthetic daily steps (default: 30)")
    p.add_argument("--synthetic", action="store_true",
                   help="generate a physics-consistent synthetic scene (offline)")
    p.add_argument("--output-dir", default="./output", help="output directory")
    p.add_argument("--quiet", action="store_true", help="suppress console output")
    p.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return process(args)
    except GeoSkillError as exc:
        print(f"[{SKILL_NAME}] ERROR [{exc.kind}] {exc.message}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"[{SKILL_NAME}] ERROR {exc}", file=sys.stderr)
        return to_exit_code(exc)


if __name__ == "__main__":
    sys.exit(main())
