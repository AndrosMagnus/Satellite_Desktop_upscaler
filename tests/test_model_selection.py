import unittest
from pathlib import Path

from app.dataset_analysis import DatasetInfo, GridSignature
from app.model_selection import recommend_execution_plan
from app.recommendation import HardwareProfile


class TestModelSelection(unittest.TestCase):
    def _sentinel_info(self) -> DatasetInfo:
        return DatasetInfo(
            path=Path("S2A_MSIL2A_20240201T104031_N0509_R008_T31TCJ_20240201T130924.tif"),
            provider="Sentinel-2",
            sensor="MSI-L2A",
            format_label="GeoTIFF",
            band_count=13,
            grid=GridSignature(
                crs="EPSG:32631",
                transform=(10.0, 0.0, 0.0, 0.0, -10.0, 0.0),
                width=256,
                height=256,
            ),
            dtype="uint16",
            nodata=None,
            scales=(1.0,) * 13,
            offsets=(0.0,) * 13,
            band_names=None,
        )

    def test_recommends_sentinel_model_with_defaults(self) -> None:
        info = self._sentinel_info()
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        plan = recommend_execution_plan(info, hardware)

        self.assertEqual(plan.model, "S2DR3")
        self.assertEqual(plan.scale, 4)
        self.assertEqual(plan.precision, "FP16")
        self.assertEqual(plan.compute, "GPU")
        self.assertEqual(plan.tiling, "Off")

    def test_safe_mode_forces_cpu(self) -> None:
        info = self._sentinel_info()
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        plan = recommend_execution_plan(
            info,
            hardware,
            compute_override="GPU",
            safe_mode=True,
        )

        self.assertEqual(plan.compute, "CPU")
        self.assertEqual(plan.scale, 2)
        self.assertEqual(plan.precision, "FP32")
        self.assertEqual(plan.tiling, "512 px")

    def test_explicit_overrides_apply(self) -> None:
        info = self._sentinel_info()
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        plan = recommend_execution_plan(
            info,
            hardware,
            model_override="Real-ESRGAN",
            scale_override=2,
            tiling_override="512 px",
            precision_override="FP32",
            compute_override="CPU",
        )

        self.assertEqual(plan.model, "Real-ESRGAN")
        self.assertEqual(plan.scale, 2)
        self.assertEqual(plan.tiling, "512 px")
        self.assertEqual(plan.precision, "FP32")
        self.assertEqual(plan.compute, "CPU")

    def test_cloud_imagery_prefers_mrdam(self) -> None:
        info = DatasetInfo(
            path=Path("cloud_dense_scene.png"),
            provider=None,
            sensor=None,
            format_label="PNG",
            band_count=3,
            grid=None,
            dtype=None,
            nodata=None,
            scales=None,
            offsets=None,
            band_names=None,
        )
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        plan = recommend_execution_plan(info, hardware)

        self.assertEqual(plan.model, "MRDAM")


if __name__ == "__main__":
    unittest.main()
