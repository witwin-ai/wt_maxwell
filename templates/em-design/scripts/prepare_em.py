"""Check and print the FDTD setup of scenes/main.wtscene.

    python scripts/prepare_em.py                     # print the setup
    python scripts/prepare_em.py --frequency-ghz 1.5 # retune solver and source, save
"""
from __future__ import annotations

import argparse
from pathlib import Path

import witwin.studio as ws

PROJECT = Path(__file__).resolve().parents[1]


def find(scene: ws.Scene, component: str) -> ws.Entity:
    for entity in scene.objects.values():
        if component in entity.components:
            return entity
    raise SystemExit(f"no entity with a {component} component in the main scene")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--frequency-ghz", type=float, help="new solve and source frequency in GHz")
    args = parser.parse_args(argv)

    project = ws.open_project(PROJECT)
    scene = project.scene()
    settings, source = find(scene, "MaxwellSolver"), find(scene, "PointDipoleSource")
    solver, dipole = settings.components["MaxwellSolver"], source.components["PointDipoleSource"]

    if args.frequency_ghz is not None:
        hz = args.frequency_ghz * 1e9
        # The source pulse is centred on the solve frequency; keep its relative width.
        dipole["st_fwidth"] = dipole["st_fwidth"] / dipole["st_frequency"] * hz
        dipole["st_frequency"] = hz
        solver["frequencies"] = [hz]
        scene.save()
        print(f"saved: solve and source at {args.frequency_ghz} GHz")

    lo, hi = solver["bounds_min"], solver["bounds_max"]
    print(f"Project {project.name}, scene {scene.id}")
    print(f"  domain        {[round(v, 3) for v in lo]} .. {[round(v, 3) for v in hi]} m, grid {solver['dl']:.3f} m")
    print(f"  boundary      {solver['absorber']}, {int(solver['num_layers'])} layers")
    print(f"  frequencies   {[f / 1e9 for f in solver['frequencies']]} GHz")
    print(f"  source        {source.name!r} at {source.transform.position}, "
          f"{dipole['st_kind']} {dipole['st_frequency'] / 1e9:.2f} GHz")
    inside = all(a <= p <= b for a, p, b in zip(lo, source.transform.position, hi))
    if not inside:
        print("  the source is outside the domain")
        return 1
    print("Ready to solve in Studio (Maxwell Settings: Solve).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
