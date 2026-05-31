"""Out-of-process Maxwell FDTD solver entry."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any, Dict


PLUGIN_PARENT = Path(__file__).resolve().parent.parent
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))

import wt_maxwell  # noqa: F401  (registers Maxwell components before Scene.from_dict)
from witwin_server.features.solvers.sdk import query, serve
from wt_maxwell.adapter.solve import SliceExtractor, SolveConfig, SolveRunner


def _solve_config(config: Dict[str, Any]) -> SolveConfig:
    return SolveConfig(
        method=str(config.get("method") or "fdtd"),
        frequencies=tuple(float(v) for v in (config.get("frequencies") or ())),
        absorber=str(config.get("absorber") or "cpml"),
        full_field_dft=bool(config.get("full_field_dft", False)),
        time_steps=(None if config.get("time_steps") is None else int(config["time_steps"])),
    )


def solve(ctx, scene, config):
    ctx.progress(0.0, "building Maxwell scene")
    result = SolveRunner.run(scene, _solve_config(config or {}))
    ctx.progress(1.0, "Maxwell solve complete")
    return result


@query("extract_slice")
def extract_slice(ctx, result, params):
    sl = SliceExtractor.extract(
        result,
        axis=str(params.get("axis") or "z"),
        position=float(params.get("position") or 0.0),
        component=str(params.get("component") or "Ez"),
        value_mode=str(params.get("value_mode") or "abs"),
        freq_index=int(params.get("freq_index") or 0),
        log_scale=bool(params.get("log_scale", False)),
    )
    return {
        "data": sl.data,
        "extent": sl.extent,
        "xlabel": sl.xlabel,
        "ylabel": sl.ylabel,
    }


@query("extract_volume")
def extract_volume(ctx, result, params):
    volume = SliceExtractor.volume(
        result,
        component=str(params.get("component") or "Ez"),
        value_mode=str(params.get("value_mode") or "abs"),
        freq_index=int(params.get("freq_index") or 0),
    )
    buf = io.BytesIO()
    import numpy as np

    volume = volume.astype(np.float32, copy=False)
    np.save(buf, volume, allow_pickle=False)
    return {
        "resultRef": ctx.result_ref(
            buf.getvalue(),
            kind="npy",
            extension=".npy",
            metadata={"format": "numpy.npy"},
        ),
        "shape": list(volume.shape),
        "dtype": str(volume.dtype),
    }


serve(solve)
