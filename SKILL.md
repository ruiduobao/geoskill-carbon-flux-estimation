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


<!-- ===== 中文原文 (Chinese Original) ===== -->

---
name: geoskill-carbon-flux-estimation
description: '基于光能利用率模型（CASA/VPM 简化）估算 GPP/NPP：GPP=PAR×FPAR×ε，ε 受温度与水分胁迫调节，NPP=GPP−自养呼吸，输出碳收支'
---

# 碳通量估算 | Carbon Flux Estimation

本 skill 用简化的**光能利用率模型**（light-use-efficiency，CASA / VPM 思路）
估算生态系统碳通量：

- **GPP**（总初级生产力）= PAR × FPAR × ε
  - PAR：光合有效辐射（MJ/m²/day）
  - FPAR：光合有效辐射吸收比例（0-1）
  - ε：实际光能利用率 = εmax × Tstress × Wstress（gC/MJ）
- **温度胁迫** Tstress：以最适温度 Topt 为峰值的双侧抛物线响应。
- **水分胁迫** Wstress：随可用水分量非线性调节。
- **自养呼吸** Ra = GPP × ra_frac(T)，温度越高呼吸占比越大。
- **NPP**（净初级生产力）= GPP − Ra。

量级经参数校准落在植被合理范围（日 GPP 约 0.5-15 gC/m²/day，NPP/GPP≈0.5）。
输出累计 GPP/NPP 栅格、逐日通量时序与碳收支 JSON。适用于区域碳收支评估、
植被生产力制图、生态模型强迫与碳源汇分析。

## 依赖

```bash
pip install 'numpy' 'rasterio' 'scipy'
```

## 使用方法

### 基本用法

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 [其他参数]
```

### 示例 1（合成数据，离线）

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --synthetic --output-dir ./out
```

### 示例 2（仅给 bbox，自动合成）

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --output-dir ./out
```

### 示例 3（更长时间序列）

```bash
python geoskill-carbon-flux-estimation.py --bbox 116.0 39.0 117.0 40.0 --synthetic --n-dates 60 --output-dir ./out
```

### 示例 4（静默模式）

```bash
python geoskill-carbon-flux-estimation.py --bbox 121.0 31.0 122.0 32.0 --synthetic --output-dir ./out --quiet
```

### 示例 5（真实栅格输入，4 波段=PAR/FPAR/温度/水分）

```bash
python geoskill-carbon-flux-estimation.py --input par_fpar_temp_water.tif --output-dir ./out
```

## 输出

| 文件 | 格式 | 说明 |
|---|---|---|
| `carbon_flux.tif` | GeoTIFF | 时段累计 GPP/NPP（2 波段，gC/m²） |
| `flux_timeseries.json` | JSON | 逐日 GPP/NPP/Ra 空间均值时序 |
| `carbon_budget.json` | JSON | 碳收支（日均/累计/NPP-GPP 比） |
| `output-manifest.json` | JSON | 运行清单 |

## 数据源 / Source

- **真实模式**：本地多波段 GeoTIFF（4 波段 = PAR/FPAR/温度/水分）。
- **合成模式**（`--synthetic` 或仅 `--bbox`）：本地生成物理一致的 PAR/FPAR/温度/水分场与时序，无需网络。

## 隐私声明 / Privacy

- 默认离线运行，`--synthetic` 模式完全无网络。
- 所有处理在本地完成，不上传用户数据。

## License

MIT
