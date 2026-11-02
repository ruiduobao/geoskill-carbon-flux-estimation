---
name: geoskill-carbon-flux-estimation
description: '基于光能利用率模型（CASA/VPM 简化）估算 GPP/NPP：GPP=PAR×FPAR×ε，ε 受温度与水分胁迫调节，NPP=GPP−自养呼吸，输出碳收支'
---

# 碳通量估算 | Carbon Flux Estimation

This skill estimates ecosystem carbon fluxes using a simplified **light-use-efficiency model** (following the CASA / VPM approach):

- **GPP** (Gross Primary Productivity) = PAR × FPAR × ε
  - PAR: photosynthetically active radiation (MJ/m²/day)
  - FPAR: fraction of photosynthetically active radiation absorbed (0-1)
  - ε: actual light-use efficiency = εmax × Tstress × Wstress (gC/MJ)
- **Temperature stress** Tstress: a two-sided parabolic response peaking at the optimum temperature Topt.
- **Water stress** Wstress: adjusted nonlinearly with available water.
- **Autotrophic respiration** Ra = GPP × ra_frac(T), where the respiration fraction increases with temperature.
- **NPP** (Net Primary Productivity) = GPP − Ra.

The magnitudes are calibrated to fall within reasonable vegetation ranges (daily GPP of approximately 0.5-15 gC/m²/day, NPP/GPP ≈ 0.5).
Outputs cumulative GPP/NPP rasters, daily flux time series, and a carbon budget JSON. Suitable for regional carbon budget assessment,
vegetation productivity mapping, ecosystem model forcing, and carbon source/sink analysis.

## Dependencies / 依赖

```bash
pip install 'numpy' 'rasterio' 'scipy'
```

## Usage / 使用方法

### Basic Usage

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 [other parameters]
```

### Example 1 (Synthetic Data, Offline)

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --synthetic --output-dir ./out
```

### Example 2 (bbox Only, Automatic Synthesis)

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --output-dir ./out
```

### Example 3 (Longer Time Series)

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --synthetic --n-dates 60 --output-dir ./out
```

### Example 4 (Quiet Mode)

```bash
python geoskill-carbon-flux-estimation.py --bbox 121.0 31.0 122.0 32.0 --synthetic --output-dir ./out --quiet
```

### Example 5 (Real Raster Input, 4 Bands=PAR/FPAR/Temperature/Water)

```bash
python geoskill-carbon-flux-estimation.py --input par_fpar_temp_water.tif --output-dir ./out
```

## Output / 输出

| File | Format | Description |
|---|---|---|
| `carbon_flux.tif` | GeoTIFF | Cumulative GPP/NPP over the period (2 bands, gC/m²) |
| `flux_timeseries.json` | JSON | Daily spatial-mean time series of GPP/NPP/Ra |
| `carbon_budget.json` | JSON | Carbon budget (daily mean/cumulative/NPP-GPP ratio) |
| `output-manifest.json` | JSON | Run manifest |

## Data Source / 数据源 / Source

- **Real mode**: local multi-band GeoTIFF (4 bands = PAR/FPAR/temperature/water).
- **Synthetic mode** (`--synthetic` or `--bbox` only): generates physically consistent PAR/FPAR/temperature/water fields and time series locally, with no network access required.

## Privacy / 隐私声明 / Privacy

- Runs offline by default; `--synthetic` mode requires no network access at all.
- All processing is performed locally; no user data is uploaded.

## License / License

MIT

---

> 中文完整版：需要时再读 [references/SKILL.zh-CN.md](references/SKILL.zh-CN.md)，不要默认全量加载。
