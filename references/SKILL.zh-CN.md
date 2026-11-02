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
