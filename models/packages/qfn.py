"""QFN package, simplified: mold body, exposed pad and perimeter leads.

A square plastic body ``size`` x ``size`` x ``height`` sits on z = 0. The
exposed (thermal / ground) pad and ``pins_per_side`` leads per side are
copper blocks ``lead_thickness`` thick, flush with the body's bottom face;
the leads also end flush with its sides. The mold has pockets where the
copper sits, so no two bodies overlap. No die, die attach or bond wires
(see ``wire_bond.py`` for a bond).

Pins follow the JEDEC convention seen from the top: pin 1 at the top of the
left side, numbered counter-clockwise. Each lead has a port anchor
``pin<N>`` at the center of its bottom (soldered) face, normal -z; the
exposed pad has ``epad`` (kind ``ground``) the same way.

Default: QFN-16, 4 x 4 x 0.85 mm, 0.65 mm pitch, 2.1 mm exposed pad (the
JEDEC MO-220 VGGD family). No design formula: the dimensions come from the
package drawing.

    python qfn.py
"""
import witwin.studio as ws

CONFIG = {"unit": "mm", "up": "z", "grid": 0.025e-3}
PARAMS = {
    "size": ws.param(4.0, unit="mm", min=0.5, max=30, description="body size (square)"),
    "height": ws.param(0.85, unit="mm", min=0.1, max=5, description="body height"),
    "pins_per_side": ws.param(4, integer=True, min=1, max=40, description="leads per side"),
    "pitch": ws.param(0.65, unit="mm", min=0.1, max=5, description="lead pitch"),
    "lead_width": ws.param(0.3, unit="mm", min=0.02, max=2, description="lead width"),
    "lead_length": ws.param(0.4, unit="mm", min=0.02, max=5, description="lead length inward from the body edge"),
    "lead_thickness": ws.param(0.2, unit="mm", min=0.01, max=1, description="lead frame thickness"),
    "epad": ws.param(2.1, unit="mm", min=0, max=30, description="exposed pad size (0: none)"),
    "eps_r": ws.param(3.8, min=1, max=20, description="mold compound relative permittivity, dimensionless"),
    "tan_delta": ws.param(0.01, min=0, max=1, description="mold compound loss tangent"),
}


def _box(x0, x1, y0, y1, z0, z1):
    from build123d import Align, Box, Pos

    return Pos(x0, y0, z0) * Box(x1 - x0, y1 - y0, z1 - z0, align=(Align.MIN, Align.MIN, Align.MIN))


def leads(p):
    """``[(pin number, (x0, x1, y0, y1), outward side normal)]`` for every lead, JEDEC order."""
    n = int(p.pins_per_side)
    half = p.size / 2.0
    span = (n - 1) * p.pitch
    if span + p.lead_width >= p.size - 2.0 * p.lead_length:
        raise ValueError("the leads do not fit along a side: reduce pins_per_side or pitch")
    offsets = [span / 2.0 - i * p.pitch for i in range(n)]   # +y to -y
    w2, l = p.lead_width / 2.0, p.lead_length
    out = []
    # Left side, top to bottom; bottom side, left to right; right side, bottom to top; top side, right to left.
    sides = [
        (lambda o: (-half, -half + l, o - w2, o + w2), (-1, 0, 0)),
        (lambda o: (-o - w2, -o + w2, -half, -half + l), (0, -1, 0)),
        (lambda o: (half - l, half, -o - w2, -o + w2), (1, 0, 0)),
        (lambda o: (o - w2, o + w2, half - l, half), (0, 1, 0)),
    ]
    pin = 1
    for rect, normal in sides:
        for o in offsets:
            out.append((pin, rect(o), normal))
            pin += 1
    return out


def build(ctx):
    from build123d import Compound

    p = ctx.params
    half, t, e = p.size / 2.0, p.lead_thickness, 0.05
    if t >= p.height:
        raise ValueError("lead_thickness must be below the body height")
    if p.epad > 0 and p.epad / 2.0 >= half - p.lead_length - 0.05:
        raise ValueError("the exposed pad overlaps the leads: reduce epad")
    items = leads(p)
    pockets, coppers, anchors = [], [], []
    for pin, (x0, x1, y0, y1), normal in items:
        coppers.append(_box(x0, x1, y0, y1, 0.0, t))
        # The pocket runs past the side and bottom faces it opens onto (cad-modeling pitfall 3).
        px0, px1 = (x0 - e if normal[0] < 0 else x0), (x1 + e if normal[0] > 0 else x1)
        py0, py1 = (y0 - e if normal[1] < 0 else y0), (y1 + e if normal[1] > 0 else y1)
        pockets.append(_box(px0, px1, py0, py1, -e, t))
        anchors.append(ws.anchor(f"pin{pin}", point=((x0 + x1) / 2, (y0 + y1) / 2, 0.0), normal=(0, 0, -1),
                                 kind="port"))
    mold = _box(-half, half, -half, half, 0.0, p.height)
    bodies = []
    if p.epad > 0:
        a = p.epad / 2.0
        pockets.append(_box(-a, a, -a, a, -e, t))
        pad = _box(-a, a, -a, a, 0.0, t)
        bodies.append(ws.Body(pad, name="epad", material="PEC", role="conductor",
                              anchors=[ws.anchor("epad", point=(0, 0, 0), normal=(0, 0, -1), kind="ground")]))
    mold = mold.cut(*pockets)
    copper_volume = sum(c.volume for c in coppers) + (p.epad ** 2 * t if p.epad > 0 else 0.0)
    expected = p.size ** 2 * p.height - copper_volume
    if abs(mold.volume - expected) > 1e-3 * expected:
        raise RuntimeError("the mold pocket boolean failed")
    body_material = {"name": "mold compound", "eps_r": p.eps_r, "tan_delta": p.tan_delta}
    return [ws.Body(mold, name="mold", material=body_material, role="dielectric",
                    anchors=[ws.anchor("top_center", point=(0, 0, p.height), normal=(0, 0, 1))]),
            ws.Body(Compound(children=coppers), name="leads", material="PEC", role="conductor", anchors=anchors),
            *bodies]


if __name__ == "__main__":
    ws.preview(build)
