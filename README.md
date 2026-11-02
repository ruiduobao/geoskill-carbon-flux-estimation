# Carbon Flux Estimation (geoskill-carbon-flux-estimation)

> Estimates GPP/NPP based on a light-use-efficiency model (simplified CASA/VPM): GPP = PAR × FPAR × ε, with ε modulated by temperature and water stress; NPP = GPP − autotrophic respiration, outputting a carbon budget

---

## 1. Overview

This skill estimates ecosystem carbon fluxes with a simplified **light-use-efficiency model** (CASA/VPM approach): - **GPP** (gross primary productivity) = PAR × FPAR × ε - PAR: photosynthetically active radiation (MJ/m²/day) - FPAR: fraction of photosynthetically active radiation absorbed (0-1) - ε: actual light-use efficiency = εmax × Tstress × Wstress (gC/MJ) - **Temperature stress** Tstress: a two-sided parabolic response peaking at the optimal temperature Topt. - **Water stress** Wstress: nonlinearly modulated by available water. - **Autotrophic respiration** Ra = GPP × ra_frac(T); the respiration fraction increases with temperature. - **NPP** (net primary productivity) = GPP − Ra. With calibrated parameters, magnitudes fall within reasonable vegetation ranges (daily GPP ≈ 0.5-15 gC/m²/day, NPP/GPP ≈ 0.5). Outputs cumulative GPP/NPP rasters, a daily flux time series and a carbon budget JSON. Suitable for regional carbon budget assessment, vegetation productivity mapping, ecological model forcing and carbon source/sink analysis.

## 3. Quick Start

```bash
pip install -r requirements.txt
python geoskill-carbon-flux-estimation.py --bbox 116 39 117 40 --synthetic --output-dir ./out
```

## 4. CLI Parameters

Run `python <skill>.py --help` for the full list. Common parameters:

| Parameter | Type | Description |
|---|---|---|
| `--bbox` | `float[4]` | WGS84 bounding box `min_lon min_lat max_lon max_lat` |
| `--input` | `path` | Local input file (GeoJSON/GeoTIFF/etc.) |
| `--output-dir` | `path` | Output directory (default `./output`) |
| `--synthetic` | `flag` | Use synthetic data instead of real input |
| `--quiet` | `flag` | Suppress non-essential stdout |

## 5. Input / Output

| File | Format | Description |
|---|---|---|
| `carbon_flux.tif` | GeoTIFF | Period-cumulative GPP/NPP (2 bands, gC/m²) |
| `flux_timeseries.json` | JSON | Daily spatially averaged time series of GPP/NPP/Ra |
| `carbon_budget.json` | JSON | Carbon budget (daily mean/cumulative/NPP-GPP ratio) |
| `output-manifest.json` | JSON | Run manifest |


## 6. Technical Principle

(see SKILL.md for details)

## 8. License

MIT License. See [`LICENSE`](./LICENSE) for full text.

---

> 中文完整版：[references/SKILL.zh-CN.md](references/SKILL.zh-CN.md)
