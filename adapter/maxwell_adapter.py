"""MaxwellAdapter — ``maxwell.Scene`` <-> studio ``Scene`` (the ``"maxwell"`` domain).

Implements the frozen ``SceneAdapter`` protocol (detect / to_studio / to_platform)
and is registered on the core ``PlatformSceneHandler`` by the plugin's ``__init__``.

It reuses the frozen base maps for the shared parts — geometry (``GeometryMap``),
transform (``TransformMap``), structure metadata (``StructureMap``) — and adds the
maxwell-specific parts: the scene config singleton (``SettingsMap``), the full
``maxwell.Material`` (``MaterialAdapter``), and (later phases) sources, monitors,
ports, and material regions.
"""
from typing import Any, List, Optional

from witwin_server import Scene, SceneObject
from witwin_server.platform_bridge import GeometryMap, StructureMap, TransformMap

from .material_adapter import MaterialAdapter
from .settings_map import MARKER_COMPONENT, SettingsMap


def _num(value: Any) -> float:
    if hasattr(value, "item"):
        return float(value.item())
    return float(value)


def _list(value: Any) -> list:
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


class MaxwellAdapter:
    """Bidirectional adapter between a ``maxwell.Scene`` and a studio ``Scene``."""

    def detect(self, scene: Any) -> bool:
        """Claim the scene iff it is a ``maxwell.Scene`` (graceful if maxwell absent)."""
        try:
            import witwin.maxwell as mw
        except ImportError:
            return False
        return isinstance(scene, mw.Scene)

    # --- platform -> studio --------------------------------------------------

    def to_studio(self, scene: Any) -> Scene:
        """Translate a ``maxwell.Scene`` into a studio ``Scene`` (batched)."""
        studio = Scene(kind="local")
        studio.begin_batch()
        studio.add_object(SettingsMap.to_studio(scene))
        for structure in scene.structures:
            obj = StructureMap.to_studio(structure)
            em = obj.get_component("EMMaterial")
            if em is not None:
                MaterialAdapter.overlay_studio(em, structure.material)
            studio.add_object(obj)
        for region in scene.material_regions:
            studio.add_object(MaterialAdapter.region_to_studio(region))
        studio.end_batch()
        return studio

    # --- studio -> platform --------------------------------------------------

    def to_platform(self, studio_scene: Scene) -> Any:
        """Rebuild a ``maxwell.Scene`` from the studio scene's objects."""
        import witwin.maxwell as mw

        settings_obj = self._find_settings(studio_scene)
        if settings_obj is None:
            raise ValueError(
                "maxwell export requires a 'Maxwell Settings' object with a "
                "MaxwellDomain component (scene domain/grid/boundary).")
        config = SettingsMap.build_config(settings_obj)
        scene = mw.Scene(
            domain=config.domain,
            grid=config.grid,
            boundary=config.boundary,
            subpixel_samples=config.subpixel_samples,
            symmetry=config.symmetry,
            device=config.device,
        )
        for obj in studio_scene.objects.values():
            if obj is settings_obj:
                continue
            if obj.get_component("MaterialRegion") is not None:
                scene.add_material_region(MaterialAdapter.region_to_platform(obj))
            elif obj.get_component("PlatformGeometry") is not None:
                scene.add_structure(self._structure_to_platform(mw, obj))
        return scene

    @staticmethod
    def _find_settings(studio_scene: Scene) -> Optional[SceneObject]:
        # The Maxwell Settings object is the one carrying a MaxwellDomain.
        for obj in studio_scene.objects.values():
            if obj.get_component(MARKER_COMPONENT) is not None:
                return obj
        return None

    @staticmethod
    def _structure_to_platform(mw: Any, obj: SceneObject) -> Any:
        # Geometry + transform via the frozen base maps; material via MaterialAdapter.
        geom = obj.get_component("PlatformGeometry")
        transform = obj.get_component("Transform")
        position = _list(transform.position)
        rotation_quat = TransformMap.euler_to_quat(transform.rotation)

        vertices = faces = None
        if str(geom.kind) == "mesh":
            mesh = obj.get_component("Mesh")
            if mesh is not None and not mesh.is_empty:
                vertices = mesh.get_vertices_numpy()
                faces = mesh.get_faces_numpy()
        geometry = GeometryMap.to_platform(geom, position, rotation_quat,
                                           vertices=vertices, faces=faces)

        em = obj.get_component("EMMaterial")
        material = MaterialAdapter.to_platform(em) if em is not None else mw.Material()

        meta = obj.get_component("StructureMeta")
        if meta is None:
            return mw.Structure(geometry, material, name=obj.name)
        return mw.Structure(
            geometry, material, name=obj.name,
            priority=int(_num(meta.priority)),
            enabled=bool(meta.enabled),
            tags=tuple(str(tag) for tag in meta.tags),
            metadata=dict(meta.metadata),
        )
