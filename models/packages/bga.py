"""BGA package, simplified: laminate substrate, mold cap and a full grid of solder balls.

The substrate (``size`` x ``size`` x ``substrate_thickness``) sits on
z = 0 with the mold cap on top of it, inset by ``mold_inset``. The solder
balls hang below z = 0: each is a sphere of ``ball_diameter`` cut flat at
z = 0 (the substrate pad) and at z = -``standoff`` (the board pad), the
shape of a collapsed joint. No die, no substrate routing.

Balls are named the JEDEC way seen from the top: rows A, B, ... from the
top (+y) edge, skipping I, O, Q, S, X and Z; columns 1, 2, ... from the
left. Each ball has a port anchor at the center of its bottom flat
(normal -z). ``depopulate`` removes a centered square of balls (0 keeps the
full grid). Default: 8 x 8 balls at 0.8 mm pitch on a 7 mm body. No design
formula: the dimensions come from the package drawing.

    python bga.py
"""
import witwin.studio as ws

CONFIG = {"unit": "mm", "up": "z", "grid": 0.025e-3, "tolerance": 0.008, "angular_tolerance": 0.35}
PARAMS = {
    "columns": ws.param(8, integer=True, min=1, max=40, description="balls along x"),
    "rows": ws.param(8, integer=True, min=1, max=40, description="balls along y"),
    "pitch": ws.param(0.8, unit="mm", min=0.2, max=3, description="ball pitch"),
    "ball_diameter": ws.param(0.45, unit="mm", min=0.05, max=1.5, description="solder sphere diameter"),
    "standoff": ws.param(0.3, unit="mm", min=0.02, max=1.5, description="ball height after reflow"),
    "depopulate": ws.param(0, integer=True, min=0, max=38, description="side of a centered square of missing balls"),
    "size": ws.param(7.0, unit="mm", min=0.5, max=60, description="body size (square)"),
    "substrate_thickness": ws.param(0.36, unit="mm", min=0.02, max=3, description="laminate substrate thickness"),
    "mold_height": ws.param(0.6, unit="mm", min=0.02, max=5, description="mold cap height"),
    "mold_inset": ws.param(0.3, unit="mm", min=0, max=10, description="mold cap inset from the substrate edge"),
    "substrate_eps_r": ws.param(4.2, min=1, max=20, description="substrate relative permittivity (BT laminate)"),
    "mold_eps_r": ws.param(3.8, min=1, max=20, description="mold compound relative permittivity"),
    "tan_delta": ws.param(0.01, min=0, max=1, description="loss tangent of both dielectrics"),
}

ROW_LETTERS = [c for c in "ABCDEFGHJKLMNPRTUVWY"]  # JEDEC JEP95: no I, O, Q, S, X, Z


def row_name(index: int) -> str:
    """JEDEC row name: A..Y, then AA, AB, ... (letters from ``ROW_LETTERS``)."""
    n = len(ROW_LETTERS)
    if index < n:
        return ROW_LETTERS[index]
    return ROW_LETTERS[index // n - 1] + ROW_LETTERS[index % n]


def balls(p):
    """``[(name, x, y)]`` of the populated balls."""
    cols, rows = int(p.columns), int(p.rows)
    skip = int(p.depopulate)
    out = []
    for r in range(rows):
        for c in range(cols):
            if skip and abs(2 * c - (cols - 1)) < skip and abs(2 * r - (rows - 1)) < skip:
                continue
            x = (c - (cols - 1) / 2.0) * p.pitch
            y = ((rows - 1) / 2.0 - r) * p.pitch
            out.append((f"{row_name(r)}{c + 1}", x, y))
    return out


def build(ctx):
    from build123d import Align, Box, Compound, Pos, Sphere

    p = ctx.params
    r = p.ball_diameter / 2.0
    if not p.standoff < p.ball_diameter:
        raise ValueError("standoff must be below the ball diameter (the ball is cut flat at both pads)")
    if p.ball_diameter >= p.pitch:
        raise ValueError("ball_diameter must be below the pitch")
    span = max(int(p.columns) - 1, int(p.rows) - 1) * p.pitch
    if span + p.ball_diameter > p.size:
        raise ValueError("the ball grid does not fit under the body: increase size")
    # One ball: a sphere centered between the two pads, cut to the standoff height.
    ball = Pos(0, 0, -p.standoff / 2.0) * Sphere(r) & Box(p.ball_diameter + 1, p.ball_diameter + 1, p.standoff,
                                                          align=(Align.CENTER, Align.CENTER, Align.MAX))
    places = balls(p)
    solder = Compound(children=[Pos(x, y, 0) * ball for _, x, y in places])
    anchors = [ws.anchor(name, point=(x, y, -p.standoff), normal=(0, 0, -1), kind="port") for name, x, y in places]
    sub = Box(p.size, p.size, p.substrate_thickness, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cap_size = p.size - 2.0 * p.mold_inset
    if cap_size <= 0:
        raise ValueError("mold_inset leaves no mold cap")
    cap = Pos(0, 0, p.substrate_thickness) * Box(cap_size, cap_size, p.mold_height,
                                                 align=(Align.CENTER, Align.CENTER, Align.MIN))
    return [
        ws.Body(sub, name="substrate", role="dielectric",
                material={"name": "BT laminate", "eps_r": p.substrate_eps_r, "tan_delta": p.tan_delta}),
        ws.Body(cap, name="mold", role="dielectric",
                material={"name": "mold compound", "eps_r": p.mold_eps_r, "tan_delta": p.tan_delta},
                anchors=[ws.anchor("top_center", point=(0, 0, p.substrate_thickness + p.mold_height),
                                   normal=(0, 0, 1))]),
        ws.Body(solder, name="balls", role="conductor", anchors=anchors,
                material={"name": "SAC305 solder", "sigma_e": 7.6e6}),
    ]


if __name__ == "__main__":
    ws.preview(build)
