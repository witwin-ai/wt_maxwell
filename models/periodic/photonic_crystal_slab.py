"""2D photonic crystal slab: a dielectric membrane with a square or triangular lattice of air holes.

The slab (thickness ``t``, default silicon) spans an ``nx`` x ``ny``
supercell of the lattice, centered on the origin in xy with its bottom face
at z = 0. ``lattice = 0`` is a square lattice: cell ``nx*a`` x ``ny*a``,
holes at the centers of the lattice squares. ``lattice = 1`` is a
triangular lattice in its rectangular cell: ``nx*a`` x ``ny*a*sqrt(3)``,
rows ``a*sqrt(3)/2`` apart and every second row shifted by ``a/2``, so
the shifted rows have half holes on the x faces that join into whole holes
when the cell is tiled. ``t_box > 0`` adds an oxide layer under the slab
(silicon-on-insulator); ``t_box = 0`` is an air-bridge membrane.

Anchors: ``cell_xmin`` / ``cell_xmax`` / ``cell_ymin`` / ``cell_ymax``
(kind ``periodic``) at mid-slab for periodic or Bloch boundaries;
``port1`` (top face, normal +z) and ``port2`` (bottom face, normal -z)
for Floquet ports.

``design`` uses the scale invariance of Maxwell's equations (Joannopoulos
et al., Photonic Crystals: Molding the Flow of Light, 2nd ed., 2008,
ch. 2): a structure that has its gap centered at normalized frequency
``u = a/lambda`` works at any wavelength with a = u * lambda. The default
u = 0.271 and r = 0.3a are the common silicon-membrane values for
1550 nm (a = 420 nm, t = 220 nm), inside the TE-like gap of a triangular
hole lattice (Johnson et al., Phys. Rev. B 60, 5751, 1999). The gap edges
move with r/a, t/a and the cladding, so take ``u_mid`` from a band solve
for your own r/a and t/a; ``design`` does not compute the band gap.

    python photonic_crystal_slab.py
"""
import math

import witwin.studio as ws

from _periodic_cells import boundary_anchors, dielectric, floquet_ports, spec_values

SEGMENTS = 48           # polygon sides of each hole
CONFIG = {"unit": "um", "up": "z", "grid": 0.02e-6}
PARAMS = {
    "a": ws.param(0.42, unit="um", min=0.01, max=1000, description="lattice constant"),
    "r": ws.param(0.126, unit="um", min=0.001, max=500, description="hole radius"),
    "t": ws.param(0.22, unit="um", min=0.001, max=100, description="slab thickness"),
    "lattice": ws.param(1, integer=True, min=0, max=1, description="0: square, 1: triangular"),
    "nx": ws.param(1, integer=True, min=1, max=50, description="lattice periods along x in the cell"),
    "ny": ws.param(1, integer=True, min=1, max=50, description="lattice periods along y (triangular: row pairs)"),
    "eps_r": ws.param(12.11, min=1, max=100, description="slab relative permittivity (Si at 1550 nm)"),
    "t_box": ws.param(0.0, unit="um", min=0, max=100, description="oxide thickness under the slab, 0 for none"),
    "eps_box": ws.param(2.085, min=1, max=100, description="oxide relative permittivity (SiO2 at 1550 nm)"),
}

DESIGN_SPEC = {
    "wavelength": ws.param(1.55, unit="um", min=0.01, max=1e5, description="free-space design wavelength"),
    "u_mid": ws.param(0.271, min=0.01, max=2, description="gap-center normalized frequency a/lambda"),
    "r_ratio": ws.param(0.3, min=0.01, max=0.49, description="hole radius over lattice constant"),
}


def design(spec=None):
    """Lattice constant a = u_mid * wavelength and r = r_ratio * a (scale invariance)."""
    v = spec_values(DESIGN_SPEC, spec)
    a = v["u_mid"] * v["wavelength"]
    return {"a": round(a, 4), "r": round(v["r_ratio"] * a, 4)}


def cell_size(p):
    """(px, py) of the supercell in the model unit."""
    a, nx, ny = p.a, int(p.nx), int(p.ny)
    return (nx * a, ny * a) if int(p.lattice) == 0 else (nx * a, ny * a * math.sqrt(3.0))


def holes(p):
    """Hole centers (x, y) in the cell; half holes on the x faces are listed on both faces."""
    a, nx, ny = p.a, int(p.nx), int(p.ny)
    px, py = cell_size(p)
    if int(p.lattice) == 0:
        return [(-px / 2 + (i + 0.5) * a, -py / 2 + (j + 0.5) * a) for j in range(ny) for i in range(nx)]
    pitch = a * math.sqrt(3.0) / 2.0
    out = []
    for j in range(2 * ny):
        y = -py / 2 + (j + 0.5) * pitch
        if j % 2 == 0:
            out += [(-px / 2 + (i + 0.5) * a, y) for i in range(nx)]
        else:
            out += [(-px / 2 + i * a, y) for i in range(nx + 1)]
    return out


def _mesh(m):
    import numpy as np

    out = m.to_mesh()
    return np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts)


def build(ctx):
    import manifold3d as m3d

    p = ctx.params
    if 2 * p.r >= p.a:
        raise ValueError("2r must be smaller than a, or neighbouring holes merge")
    px, py = cell_size(p)
    slab = m3d.Manifold.cube((px, py, p.t)).translate((-px / 2, -py / 2, 0.0))
    pad = 0.1 * p.t      # holes stick out of both faces so no skin is left
    drills = [m3d.Manifold.cylinder(p.t + 2 * pad, p.r, p.r, SEGMENTS).translate((x, y, -pad)) for x, y in holes(p)]
    slab = slab - m3d.Manifold.batch_boolean(drills, m3d.OpType.Add)
    if slab.status() != m3d.Error.NoError or slab.volume() <= 0:
        raise RuntimeError(f"hole drilling failed: {slab.status()}")
    name = "silicon" if abs(p.eps_r - 12.11) < 1e-6 else "slab"
    bodies = [ws.Body(_mesh(slab), name="slab", material=dielectric(name, p.eps_r, 0.0), role="dielectric")]
    z_bottom = 0.0
    if p.t_box > 0:
        box = m3d.Manifold.cube((px, py, p.t_box)).translate((-px / 2, -py / 2, -p.t_box))
        bodies.append(ws.Body(_mesh(box), name="box", material=dielectric("SiO2", p.eps_box, 0.0),
                              role="dielectric"))
        z_bottom = -p.t_box
    return bodies + boundary_anchors(px, py, p.t / 2.0) + floquet_ports(p.t, z_bottom)


if __name__ == "__main__":
    ws.preview(build)
