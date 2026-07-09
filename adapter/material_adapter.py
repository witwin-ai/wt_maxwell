"""Material <-> maxwell.Material (full superset) + MaterialRegion round-trip.

The maxwell adapter is the only adapter that reads the unified ``Material``
component's *advanced* EM fields (Debye/Drude/Lorentz poles for eps and mu,
diagonal anisotropy tensors, Kerr) and builds the full ``maxwell.Material``.
The base ``MaterialMap`` (core) only handles the scalar subset.

The platform marks several combinations ``NotImplemented`` (media.py / compiler).
We mirror them as adapter-side ``ValueError`` guards so the editor never emits an
invalid material (the same combinations are also surfaced as ``info_box`` warnings
on the ``Material`` component schema in core).

``MaterialRegion`` (topology optimization) round-trips its shape/bounds only; the
density tensor is the optimization design variable (runtime state), so it is never
serialized — ``to_platform`` rebuilds a zero placeholder of the stored shape.
"""
from typing import Any, List

_TOL = 1e-6


def _f(value: Any) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _complex_of(value: Any) -> complex:
    """Read the Material ``eps_r`` complex field (stored as ``[real, imag]``).

    Accepts the [real, imag] list/tensor form and, defensively, a bare real
    scalar (imag 0)."""
    value = value.tolist() if hasattr(value, "tolist") else value
    if isinstance(value, (list, tuple)):
        real = float(value[0]) if len(value) > 0 else 0.0
        imag = float(value[1]) if len(value) > 1 else 0.0
        return complex(real, imag)
    return complex(_f(value))


def _vec(value: Any) -> List[float]:
    seq = value.tolist() if hasattr(value, "tolist") else value
    return [float(v) for v in seq]


def _pairs(rows: Any) -> List[List[float]]:
    # list_field of vector2 -> [[a, b], ...]
    return [_vec(r) for r in (rows or [])]


def _triples(rows: Any) -> List[List[float]]:
    # list_field of vector3 -> [[a, b, c], ...]
    return [_vec(r) for r in (rows or [])]


def _isotropic(vec: List[float], scalar: float) -> bool:
    # True when a diagonal tensor carries no info beyond the scalar.
    return all(abs(v - scalar) <= _TOL for v in vec)


class MaterialAdapter:
    """Material <-> ``maxwell.Material`` (full superset) + MaterialRegion."""

    @staticmethod
    def to_platform(em: Any) -> Any:
        """Build a ``maxwell.Material`` from a ``Material`` component (full superset).

        The parameter is still called ``em`` for clarity of intent — these
        are the EM-side fields on the unified ``Material`` component.
        """
        import witwin.maxwell as mw

        model = str(em.model)
        debye, drude, lorentz = _pairs(em.debye_poles), _pairs(em.drude_poles), _triples(em.lorentz_poles)
        mu_debye = _pairs(em.mu_debye_poles)
        mu_drude = _pairs(em.mu_drude_poles)
        mu_lorentz = _triples(em.mu_lorentz_poles)
        poles_active = any([debye, drude, lorentz, mu_debye, mu_drude, mu_lorentz])
        tensors_active = model == "anisotropic"
        kerr = _f(em.kerr_chi3)
        kerr_active = kerr != 0.0

        MaterialAdapter._check_guards(poles_active, tensors_active, kerr_active)

        eps_c = _complex_of(em.eps_r)
        # Pass a complex eps_r to the solver when lossy; a plain real otherwise.
        eps_r = eps_c if eps_c.imag != 0.0 else eps_c.real
        eps_real = eps_c.real  # scalar used for diagonal-tensor isotropy checks
        mu_r, sigma = _f(em.mu_r), _f(em.sigma_e)
        kwargs: dict = {}
        if poles_active:
            kwargs.update(
                debye_poles=tuple(mw.DebyePole(a, b) for a, b in debye),
                drude_poles=tuple(mw.DrudePole(a, b) for a, b in drude),
                lorentz_poles=tuple(mw.LorentzPole(a, b, c) for a, b, c in lorentz),
                mu_debye_poles=tuple(mw.DebyePole(a, b) for a, b in mu_debye),
                mu_drude_poles=tuple(mw.DrudePole(a, b) for a, b in mu_drude),
                mu_lorentz_poles=tuple(mw.LorentzPole(a, b, c) for a, b, c in mu_lorentz),
            )
        if tensors_active:
            MaterialAdapter._fill_tensors(mw, kwargs, em, eps_real, mu_r, sigma)
        if kerr_active:
            kwargs["kerr_chi3"] = kerr
        name = str(em.material_name) if em.material_name else None
        return mw.Material(eps_r=eps_r, mu_r=mu_r, sigma_e=sigma, name=name, **kwargs)

    @staticmethod
    def _check_guards(poles: bool, tensors: bool, kerr: bool) -> None:
        # Mirror the platform's NotImplemented combination guards.
        if poles and tensors:
            raise ValueError(
                "Anisotropic + dispersive materials are not supported by the maxwell "
                "solver (set model to 'scalar', 'dispersive', or 'anisotropic').")
        if kerr and poles:
            raise ValueError("Kerr (kerr_chi3) cannot be combined with dispersive poles.")
        if kerr and tensors:
            raise ValueError("Kerr (kerr_chi3) cannot be combined with anisotropic tensors.")

    @staticmethod
    def _fill_tensors(mw: Any, kwargs: dict, em: Any, eps_r: float, mu_r: float, sigma: float) -> None:
        # Emit a DiagonalTensor3 only when it carries info beyond the scalar.
        et, mt, st = _vec(em.epsilon_tensor), _vec(em.mu_tensor), _vec(em.sigma_e_tensor)
        if not _isotropic(et, eps_r):
            kwargs["epsilon_tensor"] = mw.DiagonalTensor3(*et)
        if not _isotropic(mt, mu_r):
            kwargs["mu_tensor"] = mw.DiagonalTensor3(*mt)
        if not _isotropic(st, sigma):
            kwargs["sigma_e_tensor"] = mw.DiagonalTensor3(*st)

    @staticmethod
    def overlay_studio(em: Any, material: Any) -> None:
        """Overlay a ``maxwell.Material``'s advanced fields onto a ``Material`` component.

        The scalar part is already written by the base ``StructureMap``; this adds the
        dispersion / anisotropy / Kerr fields and sets ``model`` accordingly.

        ``em`` is the unified Material component (parameter name kept for clarity
        of intent — these are the EM-side fields).
        """
        if getattr(material, "is_dispersive", False):
            em.model = "dispersive"
            em.debye_poles = [[p.delta_eps, p.tau] for p in material.debye_poles]
            em.drude_poles = [[p.plasma_frequency, p.gamma] for p in material.drude_poles]
            em.lorentz_poles = [[p.delta_eps, p.resonance_frequency, p.gamma]
                                for p in material.lorentz_poles]
            em.mu_debye_poles = [[p.delta_eps, p.tau] for p in material.mu_debye_poles]
            em.mu_drude_poles = [[p.plasma_frequency, p.gamma] for p in material.mu_drude_poles]
            em.mu_lorentz_poles = [[p.delta_eps, p.resonance_frequency, p.gamma]
                                   for p in material.mu_lorentz_poles]
        if getattr(material, "is_anisotropic", False):
            em.model = "anisotropic"
            em.epsilon_tensor = MaterialAdapter._tensor_or_iso(material.epsilon_tensor, _complex_of(em.eps_r).real)
            em.mu_tensor = MaterialAdapter._tensor_or_iso(material.mu_tensor, _f(em.mu_r))
            em.sigma_e_tensor = MaterialAdapter._tensor_or_iso(material.sigma_e_tensor, _f(em.sigma_e))
        if getattr(material, "is_nonlinear", False):
            em.kerr_chi3 = float(material.kerr_chi3)

    @staticmethod
    def _tensor_or_iso(tensor: Any, scalar: float) -> List[float]:
        # DiagonalTensor3 -> its diagonal; None -> isotropic [scalar]*3 (lossless).
        if tensor is None:
            return [scalar, scalar, scalar]
        return list(tensor.as_tuple())

    # --- MaterialRegion ------------------------------------------------------

    @staticmethod
    def region_to_studio(region: Any) -> Any:
        """Build a region ``SceneObject`` (Box geometry + MaterialRegion component)."""
        from witwin_server import SceneObject
        from witwin_server.features.platform.bridge import GeometryMap
        from witwin_server.core.components import PlatformGeometryComponent
        from witwin_server.core.components.mesh import DRJIT_AVAILABLE
        import numpy as np

        from ..components.materials import MaterialRegionComponent

        sg = GeometryMap.to_studio(region.geometry)
        obj = SceneObject(name=region.name or "MaterialRegion", mesh_type="Custom")
        GeometryMap.fill_component(obj.add_component(PlatformGeometryComponent()), sg)
        if sg.vertices is not None and sg.faces is not None and DRJIT_AVAILABLE:
            obj.get_component("Mesh").set_mesh_data(sg.vertices, sg.faces.astype(np.uint32), notify=False)
        transform = obj.get_component("Transform")
        transform.position = sg.position

        comp = obj.add_component(MaterialRegionComponent())
        comp.region_name = region.name or ""
        comp.basis = str(region.basis)
        comp.bounds = list(region.bounds)
        comp.eps_bounds = list(region.eps_bounds)
        comp.mu_bounds = list(region.mu_bounds)
        shape = tuple(int(s) for s in region.density.shape)
        comp.density_nx, comp.density_ny, comp.density_nz = shape
        if region.filter_radius is not None:
            comp.use_filter = True
            comp.filter_radius = float(region.filter_radius)
        if region.projection_beta is not None:
            comp.use_projection = True
            comp.projection_beta = float(region.projection_beta)
        comp.symmetry = region.symmetry or ""
        return obj

    @staticmethod
    def region_to_platform(obj: Any) -> Any:
        """Rebuild a ``maxwell.MaterialRegion`` from a region object (zero density)."""
        import torch
        import witwin.maxwell as mw
        from witwin_server.features.platform.bridge import GeometryMap, TransformMap

        comp = obj.get_component("MaterialRegion")
        geom = obj.get_component("PlatformGeometry")
        transform = obj.get_component("Transform")
        position = _vec(transform.position)
        rotation_quat = TransformMap.euler_to_quat(transform.rotation)
        geometry = GeometryMap.to_platform(geom, position, rotation_quat)

        shape = (int(comp.density_nx), int(comp.density_ny), int(comp.density_nz))
        kwargs: dict = {}
        if bool(comp.use_filter):
            kwargs["filter_radius"] = _f(comp.filter_radius)
        if bool(comp.use_projection):
            kwargs["projection_beta"] = _f(comp.projection_beta)
        symmetry = str(comp.symmetry) if comp.symmetry else None
        return mw.MaterialRegion(
            name=str(comp.region_name),
            geometry=geometry,
            density=torch.zeros(shape, dtype=torch.float32),
            basis=str(comp.basis),
            bounds=tuple(_vec(comp.bounds)),
            eps_bounds=tuple(_vec(comp.eps_bounds)),
            mu_bounds=tuple(_vec(comp.mu_bounds)),
            symmetry=symmetry,
            **kwargs,
        )
