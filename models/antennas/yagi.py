"""Yagi-Uda array: reflector, gap-fed driven dipole and N directors of round wire.

Geometry (Z-up, mm): every element is a wire parallel to z, centred at
z = 0, and the elements stand along the +x boom line at y = 0 (no boom is
modelled: use a non-conducting boom or add one yourself). The reflector is
at x = -ref_space, the driven element at x = 0 with a feed gap at its
centre, and director i at x = i * dir_space. Beam (end-fire) towards +x;
polarization linear along z.

Bodies: ``reflector``, ``driven`` (two arms), ``directors`` (all of them).

Anchors: ``feed`` (port in the driven gap, normal +z, on ``driven``);
loose ``front`` (tip of the last director's axis) and ``back``
(reflector axis).

``design(spec)``: starting values close to Viezbicke, *Yagi Antenna Design*,
NBS Technical Note 688 (1976), as tabulated in Balanis, *Antenna Theory*,
3rd ed., section 10.3.3 (d/lambda = 0.0085): reflector 0.482 lambda at
0.2 lambda behind the driven element, first director 0.428 lambda, each
further director 0.004 lambda shorter, directors 0.25 lambda apart. The
driven element is the induced-EMF resonant length of the wire (eq. 8-60b).
Mutual coupling shifts the driven impedance; tune in the solver.

Validation grid: ``suggested_grid`` = min(lambda0/20 at f0, gap, wire radius).
"""
import witwin.studio as ws

import _antenna_common as ac

CONFIG = {"unit": "mm", "up": "z"}

PARAMS = {
    "f0": ws.param(2.45e9, unit="Hz", min=1e6, max=1e11, description="design frequency (grid)"),
    "n_directors": ws.param(3, integer=True, min=0, max=40, description="number of directors"),
    "ref_len": ws.param(58.98, unit="mm", min=1, max=1e5, description="reflector length"),
    "drv_len": ws.param(57.28, unit="mm", min=1, max=1e5, description="driven element tip-to-tip length"),
    "dir_len": ws.param(52.37, unit="mm", min=1, max=1e5, description="first director length"),
    "dir_taper": ws.param(0.49, unit="mm", min=0, max=1e4, description="length reduction per further director"),
    "ref_space": ws.param(24.47, unit="mm", min=0.5, max=1e5, description="reflector to driven element spacing"),
    "dir_space": ws.param(30.59, unit="mm", min=0.5, max=1e5, description="spacing driven-to-first and between directors"),
    "wire_d": ws.param(1.04, unit="mm", min=0.01, max=1000, description="element wire diameter"),
    "gap": ws.param(1.22, unit="mm", min=0.01, max=1000, description="feed gap of the driven element"),
    "sections": ws.param(16, integer=True, min=6, max=64, description="sides of the wire cross-section"),
}

DESIGN_SPEC = {
    "f0": ws.param(2.45e9, unit="Hz", description="design frequency"),
    "n_directors": ws.param(3, description="number of directors"),
    "d_over_lambda": ws.param(0.0085, description="wire diameter / lambda0 (NBS TN-688 tables use 0.0085)"),
}


def design(spec=None):
    """PARAMS overrides for a Yagi-Uda at spec f0."""
    s = ac.spec_values(DESIGN_SPEC, spec)
    f = s["f0"]
    lam = ac.wavelength_mm(f)
    d = s["d_over_lambda"] * lam
    return {"f0": f, "n_directors": int(round(s["n_directors"])), "wire_d": ac.round_to(d),
            "ref_len": ac.round_to(0.482 * lam), "drv_len": ac.round_to(ac.dipole_resonant_length(f, d / 2)),
            "dir_len": ac.round_to(0.428 * lam), "dir_taper": ac.round_to(0.004 * lam),
            "ref_space": ac.round_to(0.2 * lam), "dir_space": ac.round_to(0.25 * lam),
            "gap": ac.round_to(0.01 * lam)}


def suggested_grid(p):
    """Grid step in mm: min(lambda0/20 at f0, gap, wire radius)."""
    return ac.suggested_grid(p["f0"], p["gap"], p["wire_d"] / 2)


def build(ctx):
    p = ctx.params
    r, n, sec = p["wire_d"] / 2, int(p["n_directors"]), int(p["sections"])
    if p["drv_len"] <= p["gap"]:
        raise ValueError("drv_len must exceed gap")

    def wire(x, length):
        return ac.cylinder((x, 0, -length / 2), (x, 0, length / 2), r, sec)

    xr = -p["ref_space"]
    lo, hi = p["gap"] / 2, p["drv_len"] / 2
    driven = ac.merge([ac.cylinder((0, 0, lo), (0, 0, hi), r, sec), ac.cylinder((0, 0, -hi), (0, 0, -lo), r, sec)])
    out = [
        ws.Body(wire(xr, p["ref_len"]), name="reflector", material="PEC", role="conductor"),
        ws.Body(driven, name="driven", material="PEC", role="conductor",
                anchors=[ws.anchor("feed", point=(0, 0, 0), normal=(0, 0, 1), kind="port")]),
        ws.anchor("back", point=(xr, 0, 0), normal=(-1, 0, 0)),
    ]
    x_last = 0.0
    if n:
        dirs = []
        for i in range(n):
            length = p["dir_len"] - i * p["dir_taper"]
            if length <= 0:
                raise ValueError(f"director {i + 1} has non-positive length; reduce dir_taper")
            x_last = (i + 1) * p["dir_space"]
            dirs.append(wire(x_last, length))
        out.append(ws.Body(ac.merge(dirs), name="directors", material="PEC", role="conductor"))
    out.append(ws.anchor("front", point=(x_last, 0, 0), normal=(1, 0, 0)))
    return out


if __name__ == "__main__":
    ws.preview(build)
