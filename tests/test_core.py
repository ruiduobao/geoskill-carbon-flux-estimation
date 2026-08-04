"""Core algorithm tests for carbon-flux-estimation (light-use-efficiency model)."""
import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import mod as cf


class TestTemperatureStress:
    def test_peak_at_optimum(self):
        f = cf.temperature_stress(np.array([cf.T_OPT]))
        assert abs(float(f[0]) - 1.0) < 1e-9

    def test_zero_at_bounds(self):
        f = cf.temperature_stress(np.array([cf.T_MIN, cf.T_MAX]))
        assert float(f[0]) == 0.0
        assert abs(float(f[1])) < 1e-9

    def test_monotonic_around_optimum(self):
        temps = np.linspace(cf.T_MIN + 1, cf.T_MAX - 1, 100)
        f = cf.temperature_stress(temps)
        # 上升段递增，下降段递减
        opt_idx = np.argmin(np.abs(temps - cf.T_OPT))
        assert np.all(np.diff(f[:opt_idx]) >= -1e-9)
        assert np.all(np.diff(f[opt_idx:]) <= 1e-9)

    def test_cold_reduces(self):
        warm = cf.temperature_stress(np.array([25.0]))
        cold = cf.temperature_stress(np.array([5.0]))
        assert float(cold[0]) < float(warm[0])


class TestWaterStress:
    def test_range_01(self):
        w = np.linspace(0, 1, 50)
        f = cf.water_stress(w)
        assert f.min() >= 0.0
        assert f.max() <= 1.0

    def test_monotonic(self):
        w = np.linspace(0, 1, 50)
        f = cf.water_stress(w)
        assert np.all(np.diff(f) >= -1e-9)

    def test_wet_greater_than_dry(self):
        assert float(cf.water_stress(np.array([0.9]))[0]) > \
               float(cf.water_stress(np.array([0.1]))[0])


class TestEfficiency:
    def test_max_at_optimal_conditions(self):
        eps = cf.actual_efficiency(np.array([cf.T_OPT]), np.array([1.0]))
        assert abs(float(eps[0]) - cf.EPS_MAX) < 1e-9

    def test_reduced_under_stress(self):
        good = cf.actual_efficiency(np.array([25.0]), np.array([0.9]))
        bad = cf.actual_efficiency(np.array([40.0]), np.array([0.1]))
        assert float(bad[0]) < float(good[0])


class TestGPP:
    def test_gpp_equals_par_fpar_eps(self):
        """验证 GPP = PAR × FPAR × ε 的精确关系。"""
        par = np.full((8, 8), 30.0)
        fpar = np.full((8, 8), 0.6)
        temp = np.full((8, 8), 25.0)
        water = np.full((8, 8), 1.0)
        g = cf.gpp(par, fpar, temp, water)
        eps = cf.actual_efficiency(temp, water)
        expected = par * fpar * eps
        np.testing.assert_allclose(g, expected)

    def test_high_fpar_warmer_gives_high_gpp(self):
        """高 FPAR + 适宜温度 → 更高 GPP。"""
        par = np.full((4, 4), 30.0)
        temp = np.full((4, 4), 25.0)
        water = np.full((4, 4), 0.9)
        high = cf.gpp(par, np.full((4, 4), 0.8), temp, water)
        low = cf.gpp(par, np.full((4, 4), 0.2), temp, water)
        assert high.mean() > low.mean()

    def test_magnitude_reasonable(self):
        """日 GPP 量级落在植被合理范围（约 0.5-20 gC/m²/day）。"""
        par = np.full((4, 4), 35.0)
        fpar = np.full((4, 4), 0.7)
        temp = np.full((4, 4), 25.0)
        water = np.full((4, 4), 0.8)
        g = cf.gpp(par, fpar, temp, water)
        mean = float(g.mean())
        assert 0.5 < mean < 20.0


class TestNPP:
    def test_npp_less_than_gpp(self):
        par = np.full((8, 8), 30.0)
        fpar = np.full((8, 8), 0.6)
        temp = np.full((8, 8), 25.0)
        water = np.full((8, 8), 0.9)
        g, nv = cf.npp(par, fpar, temp, water)
        assert np.all(nv < g)
        assert np.all(nv > 0)

    def test_ra_increases_with_temp(self):
        """高温下自养呼吸占比更高。"""
        g = np.full((4, 4), 10.0)
        ra_cool = cf.autotrophic_respiration(g, np.full((4, 4), 10.0))
        ra_warm = cf.autotrophic_respiration(g, np.full((4, 4), 35.0))
        assert ra_warm.mean() > ra_cool.mean()


class TestFluxSeries:
    def test_shapes(self):
        n, H, W = 5, 8, 8
        par = np.full((n, H, W), 30.0)
        fpar = np.full((n, H, W), 0.6)
        temp = np.full((n, H, W), 25.0)
        water = np.full((n, H, W), 0.8)
        s = cf.compute_flux_series(par, fpar, temp, water)
        assert s["GPP"].shape == (n, H, W)
        assert s["NPP"].shape == (n, H, W)
        assert s["Ra"].shape == (n, H, W)

    def test_shape_mismatch_raises(self):
        with pytest.raises(cf.ValidationError):
            cf.compute_flux_series(np.zeros((3, 4, 4)), np.zeros((3, 4, 5)),
                                   np.zeros((3, 4, 4)), np.zeros((3, 4, 4)))

    def test_bad_ndim_raises(self):
        with pytest.raises(cf.ValidationError):
            cf.compute_flux_series(np.zeros((4, 4)), np.zeros((4, 4)),
                                   np.zeros((4, 4)), np.zeros((4, 4)))


class TestSynthetic:
    def test_shapes(self):
        met = cf.generate_synthetic([116, 39, 117, 40], n_dates=20)
        assert met["par"].shape == (20, 64, 64)
        assert met["fpar"].shape == (20, 64, 64)
        assert len(met["info"]["dates"]) == 20

    def test_fpar_range(self):
        met = cf.generate_synthetic([116, 39, 117, 40], n_dates=10)
        assert met["fpar"].min() >= 0.0
        assert met["fpar"].max() <= 1.0


class TestGeoTiffIO:
    def test_roundtrip(self, tmp_path):
        cube = np.random.uniform(0, 15, (2, 16, 16)).astype(np.float32)
        bbox = [116.0, 39.0, 117.0, 40.0]
        path = str(tmp_path / "c.tif")
        cf.write_geotiff(path, cube, bbox)
        back, rb = cf.read_geotiff(path)
        assert back.shape == cube.shape
        np.testing.assert_allclose(rb, bbox, atol=1e-6)

    def test_read_missing_raises(self):
        with pytest.raises(cf.UsageError):
            cf.read_geotiff("/nonexistent/c.tif")
