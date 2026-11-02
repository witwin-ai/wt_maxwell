"""Out-of-process Maxwell FDTD solver entry."""
from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any, Dict


def _import_this_plugin() -> None:
    """Import this folder as the ``wt_maxwell`` package.

    The folder name is not always ``wt_maxwell`` (a worktree, a cloud store
    ``<id>/<version>/`` folder), so putting the parent on ``sys.path`` and
    importing by name can load another checkout of the Plugin, or none.
    """
    import importlib.util

    root = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "wt_maxwell", root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["wt_maxwell"] = module
    spec.loader.exec_module(module)  # registers Maxwell components before Scene.from_dict


_import_this_plugin()
from witwin.studio.solver import query, serve
from wt_maxwell.adapter.solve import (
    SliceExtractor,
    SolveConfig,
    SolveRunner,
)


def solve(ctx, scene, config):
    ctx.progress(0.0, "building Maxwell scene")
    result = SolveRunner.run(scene, SolveConfig.for_scene(scene, config))
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
