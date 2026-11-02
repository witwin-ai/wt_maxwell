"""Out-of-process Maxwell FDTD solver entry."""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path
from typing import Any, Dict


def _ensure_mesh_sdf_runtime_env() -> None:
    """Expose conda/CUDA paths before importing torch/slang-backed modules."""
    env_prefix = Path(sys.executable).resolve().parent
    conda_prefix = env_prefix if (env_prefix / "python.exe").exists() else Path(os.environ.get("CONDA_PREFIX", env_prefix))

    cuda_root = os.environ.get("CUDA_PATH")
    if not cuda_root:
        candidates = sorted(
            Path("C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA").glob("v*"),
            reverse=True,
        )
        if candidates:
            cuda_root = str(candidates[0])
            os.environ["CUDA_PATH"] = cuda_root

    def prepend_env(name: str, entries: list[Path]) -> None:
        current = os.environ.get(name, "")
        parts = [part for part in current.split(os.pathsep) if part]
        seen = {os.path.normcase(part) for part in parts}
        prefix: list[str] = []
        for entry in entries:
            if not entry.exists():
                continue
            text = str(entry)
            key = os.path.normcase(text)
            if key in seen:
                continue
            prefix.append(text)
            seen.add(key)
        if prefix:
            os.environ[name] = os.pathsep.join(prefix + parts)

    path_entries = [conda_prefix, conda_prefix / "Library" / "bin", conda_prefix / "Scripts"]
    lib_entries = [conda_prefix / "Library" / "lib"]
    include_entries = [conda_prefix / "Library" / "include"]
    if cuda_root:
        cuda_path = Path(cuda_root)
        path_entries.append(cuda_path / "bin")
        lib_entries.append(cuda_path / "lib" / "x64")
        include_entries.append(cuda_path / "include")

    prepend_env("PATH", path_entries)
    prepend_env("LIB", lib_entries)
    prepend_env("INCLUDE", include_entries)


_ensure_mesh_sdf_runtime_env()


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
