"""Bond wire between two points with a JEDEC-style 4-point loop profile and a ball bond.

The loop lies in the vertical plane through both bonds. Its control points
follow the 4-point bond-wire profile used by the JEDEC-style bond-wire
models of EM tools (parameters h1, alpha, beta):

- P0: the first (ball) bond at ``(x1, y1, z1)``;
- P1: ``loop_height`` above P0, reached at ``alpha`` degrees from the
  horizontal toward the second bond;
- P2: at the same height as P1, from where the wire descends to the second
  bond at ``beta`` degrees from the horizontal;
- P3: the second (stitch) bond at ``(x2, y2, z2)``.

The corners at P1 and P2 are rounded with ``bend_radius`` (shrunk when a
segment is too short), and the wire is a closed round tube of ``diameter``.
With ``ball_diameter > 0`` a ball bond (a disc ``ball_height`` high) sits
under the first bond and is fused with the wire (manifold3d boolean).

Ports: ``port1`` at the first bond and ``port2`` at the second, both normal
-z (into the pads). Default: 25 um gold wire from a die pad at
(0, 0, 0.25) mm to a lead at (1.2, 0, 0) mm. No design formula.

    python wire_bond.py
"""
import math

import witwin.studio as ws

CONFIG = {"unit": "mm", "up": "z", "grid": 5e-6}
PARAMS = {
    "x1": ws.param(0.0, unit="mm", min=-100, max=100, description="first (ball) bond x"),
    "y1": ws.param(0.0, unit="mm", min=-100, max=100, description="first (ball) bond y"),
    "z1": ws.param(0.25, unit="mm", min=-100, max=100, description="first (ball) bond z (die pad surface)"),
    "x2": ws.param(1.2, unit="mm", min=-100, max=100, description="second (stitch) bond x"),
    "y2": ws.param(0.0, unit="mm", min=-100, max=100, description="second (stitch) bond y"),
    "z2": ws.param(0.0, unit="mm", min=-100, max=100, description="second (stitch) bond z (lead surface)"),
    "loop_height": ws.param(0.15, unit="mm", min=0.005, max=10, description="h1: loop top above the first bond"),
    "alpha": ws.param(80, unit="deg", min=20, max=90, description="rise angle at the first bond, from horizontal"),
    "beta": ws.param(30, unit="deg", min=5, max=90, description="descent angle at the second bond, from horizontal"),
    "diameter": ws.param(0.025, unit="mm", min=0.005, max=1, description="wire diameter"),
    "bend_radius": ws.param(0.05, unit="mm", min=0.0, max=5, description="corner rounding radius at P1 and P2"),
    "ball_diameter": ws.param(0.06, unit="mm", min=0.0, max=1, description="ball bond diameter (0: none)"),
    "ball_height": ws.param(0.015, unit="mm", min=0.001, max=1, description="ball bond height"),
    "sigma": ws.param(4.1e7, min=1e5, max=1e8, description="wire conductivity, S/m (gold 4.1e7)"),
}

SEGMENTS = 16          # facets around the wire
ARC_STEPS = 10         # samples per rounded corner


def profile(p):
    """Control points P0..P3 as 3D tuples (model unit) of the JEDEC-style 4-point loop."""
    p0 = (p.x1, p.y1, p.z1)
    p3 = (p.x2, p.y2, p.z2)
    dx, dy = p.x2 - p.x1, p.y2 - p.y1
    span = math.hypot(dx, dy)
    if span <= 0:
        raise ValueError("the two bonds must be apart horizontally")
    ux, uy = dx / span, dy / span
    top = p.z1 + p.loop_height
    if top <= p.z2:
        raise ValueError("loop_height must bring the loop above the second bond")
    s1 = p.loop_height / math.tan(math.radians(p.alpha)) if p.alpha < 90 else 0.0
    s2 = span - (top - p.z2) / math.tan(math.radians(p.beta)) if p.beta < 90 else span
    if s2 < s1:
        raise ValueError("the loop does not fit between the bonds at these angles: lower loop_height, "
                         "or steepen alpha or beta")
    p1 = (p.x1 + ux * s1, p.y1 + uy * s1, top)
    p2 = (p.x1 + ux * s2, p.y1 + uy * s2, top)
    return [p0, p1, p2, p3]


def _centerline(points, radius):
    """Polyline through ``points`` with each interior corner replaced by a circular arc of ``radius``."""
    import numpy as np

    pts = [np.asarray(q, dtype=float) for q in points]
    pts = [q for i, q in enumerate(pts) if i == 0 or np.linalg.norm(q - pts[i - 1]) > 1e-12]
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        a, b, c = pts[i - 1], pts[i], pts[i + 1]
        t_in = (b - a) / np.linalg.norm(b - a)
        t_out = (c - b) / np.linalg.norm(c - b)
        turn = math.acos(max(-1.0, min(1.0, float(t_in @ t_out))))
        if turn < 1e-6 or radius <= 0:
            out.append(b)
            continue
        # Tangent length of the fillet; never more than half of either segment.
        reach = min(radius * math.tan(turn / 2.0), 0.5 * np.linalg.norm(b - a), 0.5 * np.linalg.norm(c - b))
        r = reach / math.tan(turn / 2.0)
        start, end = b - t_in * reach, b + t_out * reach
        # Center direction: the part of t_out normal to t_in (toward the inside of the corner).
        normal = t_out - (t_out @ t_in) * t_in
        normal /= np.linalg.norm(normal)
        center = start + normal * r
        for k in range(ARC_STEPS + 1):
            ang = turn * k / ARC_STEPS
            out.append(center + r * (-math.cos(ang) * normal + math.sin(ang) * t_in))
    out.append(pts[-1])
    return np.array(out)


def _tube(path, radius):
    """Closed tube mesh around ``path`` (N x 3): parallel-transport frames, flat end caps."""
    import numpy as np

    n = len(path)
    tangents = np.gradient(path, axis=0)
    tangents /= np.linalg.norm(tangents, axis=1)[:, None]
    ref = np.array([0.0, 0.0, 1.0]) if abs(tangents[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    normal = np.cross(tangents[0], ref)
    normal /= np.linalg.norm(normal)
    rings = []
    for i in range(n):
        if i:
            # Parallel transport: remove the component along the new tangent.
            normal = normal - tangents[i] * (normal @ tangents[i])
            normal /= np.linalg.norm(normal)
        binormal = np.cross(tangents[i], normal)
        ang = np.linspace(0.0, 2.0 * math.pi, SEGMENTS, endpoint=False)
        rings.append(path[i] + radius * (np.cos(ang)[:, None] * normal + np.sin(ang)[:, None] * binormal))
    verts = np.vstack(rings + [path[0][None, :], path[-1][None, :]])
    faces = []
    m = SEGMENTS
    for i in range(n - 1):
        for j in range(m):
            a, b = i * m + j, i * m + (j + 1) % m
            c, d = (i + 1) * m + j, (i + 1) * m + (j + 1) % m
            faces += [[a, b, d], [a, d, c]]
    start, end = n * m, n * m + 1
    for j in range(m):
        faces.append([start, (j + 1) % m, j])
        faces.append([end, (n - 1) * m + j, (n - 1) * m + (j + 1) % m])
    faces = np.array(faces, dtype=np.int64)
    # Orient outward: flip if the signed volume is negative.
    a, b, c = verts[faces[:, 0]], verts[faces[:, 1]], verts[faces[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        faces = faces[:, ::-1]
    return verts, faces


def build(ctx):
    import numpy as np

    p = ctx.params
    points = profile(p)
    path = _centerline(points, p.bend_radius)
    verts, faces = _tube(path, p.diameter / 2.0)
    mesh = (verts, faces)
    if p.ball_diameter > 0:
        if p.ball_diameter <= p.diameter:
            raise ValueError("ball_diameter must exceed the wire diameter")
        import manifold3d as m3d

        wire = m3d.Manifold(m3d.Mesh(vert_properties=np.asarray(verts, dtype=np.float32),
                                     tri_verts=np.asarray(faces, dtype=np.uint32)))
        if wire.status() != m3d.Error.NoError:
            raise RuntimeError(f"the wire tube is not a closed manifold: {wire.status()}")
        ball = m3d.Manifold.cylinder(p.ball_height, p.ball_diameter / 2.0, p.ball_diameter / 2.0, 4 * SEGMENTS)
        ball = ball.translate((p.x1, p.y1, p.z1))
        fused = (wire + ball).to_mesh()
        mesh = (np.asarray(fused.vert_properties)[:, :3], np.asarray(fused.tri_verts))
    gold = {"name": "gold" if abs(p.sigma - 4.1e7) < 1 else "bond wire", "sigma_e": p.sigma}
    return ws.Body(mesh, name="wire", material=gold, role="conductor", anchors=[
        ws.anchor("port1", point=points[0], normal=(0, 0, -1), kind="port"),
        ws.anchor("port2", point=points[-1], normal=(0, 0, -1), kind="port"),
        ws.anchor("loop_top", point=points[1]),
    ])


if __name__ == "__main__":
    ws.preview(build)
