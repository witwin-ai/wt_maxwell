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

import numpy as np
from scipy.spatial.transform import Rotation

from witwin_server.api import (
    Scene,
    SceneObject,
    GeometryMap,
    MaterialMap,
    StructureMap,
    TransformMap,
    get_world_transform,
)

from .common import render_mesh_arrays
from .material_adapter import MaterialAdapter
from .monitor_map import MONITOR_COMPONENTS, MonitorMap
from .port_map import PORT_COMPONENTS, PortMap
from .settings_map import LEGACY_MARKER_COMPONENT, MARKER_COMPONENT, SettingsMap
from .source_map import SOURCE_COMPONENTS, SourceMap


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
        studio = Scene()
        studio.begin_batch()
        studio.add_object(SettingsMap.to_studio(scene))
        for structure in scene.structures:
            studio.add_object(self._structure_to_studio(structure))
        for source in scene.sources:
            studio.add_object(SourceMap.to_studio(source))
        for monitor in scene.monitors:
            studio.add_object(MonitorMap.to_studio(monitor))
        for port in scene.ports:
            studio.add_object(PortMap.to_studio(port))
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
                "MaxwellSolver component (scene domain/grid/boundary).")
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
                continue
            elif self._has_any(obj, SOURCE_COMPONENTS):
                scene.add_source(SourceMap.to_platform(obj))
                continue
            elif self._has_any(obj, MONITOR_COMPONENTS):
                scene.add_monitor(MonitorMap.to_platform(obj))
                continue
            elif self._has_any(obj, PORT_COMPONENTS):
                scene.add_port(PortMap.to_platform(obj))
                continue

            if not obj.visible:
                continue

            structure = None
            if render_mesh_arrays(obj) is not None:
                structure = self._mesh_to_platform_structure(mw, obj)

            if structure is None and obj.get_component("PlatformGeometry") is not None:
                if self._has_nonunit_scale(obj):
                    structure = self._scaled_geometry_to_platform_structure(mw, obj)
                if structure is None:
                    structure = self._structure_to_platform(mw, obj)

            if structure is not None:
                scene.add_structure(structure)
        return scene

    @staticmethod
    def _structure_to_studio(structure: Any) -> SceneObject:
        """Build user-facing Studio geometry for a Maxwell structure."""
        obj = MaxwellAdapter._native_structure_to_studio(structure)
        if obj is not None:
            return obj

        obj = StructureMap.to_studio(structure)
        material_comp = obj.get_component("Material")
        if material_comp is not None:
            MaterialAdapter.overlay_studio(material_comp, structure.material)
        MaxwellAdapter._strip_platform_components_if_mesh_backed(obj)
        return obj

    @staticmethod
    def _native_structure_to_studio(structure: Any) -> Optional[SceneObject]:
        geometry = structure.geometry
        kind = str(geometry.kind)
        if kind == "box":
            obj = SceneObject(name=structure.name or "Structure", mesh_type="Cube")
            obj.get_component("Transform").scale = _list(geometry.size)
        elif kind == "sphere":
            radius = _num(geometry.radius)
            obj = SceneObject(name=structure.name or "Structure", mesh_type="Sphere")
            obj.get_component("Transform").scale = [radius * 2.0] * 3
        elif kind in {"cylinder", "cone"} and str(geometry.axis).lower() == "z":
            radius = _num(geometry.radius)
            height = _num(geometry.height)
            mesh_type = "Cylinder" if kind == "cylinder" else "Cone"
            obj = SceneObject(name=structure.name or "Structure", mesh_type=mesh_type)
            obj.get_component("Transform").scale = [radius * 2.0, radius * 2.0, height]
        else:
            return None

        transform = obj.get_component("Transform")
        transform.position = _list(geometry.position)
        transform.rotation = TransformMap.quat_to_euler(_list(geometry.rotation))
        obj.visible = bool(structure.enabled)
        material_comp = obj.get_component("Material")
        if material_comp is not None:
            MaterialMap.fill_component(material_comp, MaterialMap.to_studio(structure.material))
            MaterialAdapter.overlay_studio(material_comp, structure.material)
        return obj

    @staticmethod
    def _strip_platform_components_if_mesh_backed(obj: SceneObject) -> None:
        mesh = obj.get_component("Mesh")
        if mesh is None or mesh.is_empty:
            return
        obj.remove_component("PlatformGeometry")
        obj.remove_component("StructureMeta")

    @staticmethod
    def _has_any(obj: SceneObject, names: tuple) -> bool:
        # True if the object carries any of the named components.
        return any(obj.get_component(name) is not None for name in names)

    @staticmethod
    def _has_nonunit_scale(obj: SceneObject) -> bool:
        transform = obj.get_component("Transform")
        if transform is None:
            return False
        return any(abs(_num(axis) - 1.0) > 1e-6 for axis in _list(transform.scale))

    @staticmethod
    def _find_settings(studio_scene: Scene) -> Optional[SceneObject]:
        # The Maxwell Settings object is the one carrying a MaxwellSolver.
        for obj in studio_scene.objects.values():
            if obj.get_component(MARKER_COMPONENT) is not None:
                return obj
        for obj in studio_scene.objects.values():
            if obj.get_component(LEGACY_MARKER_COMPONENT) is not None:
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
            mesh_arrays = render_mesh_arrays(obj)
            if mesh_arrays is not None:
                vertices, faces = mesh_arrays
        geometry = GeometryMap.to_platform(geom, position, rotation_quat,
                                           vertices=vertices, faces=faces)
        return MaxwellAdapter._structure_from_geometry(mw, obj, geometry)

    @staticmethod
    def _structure_from_geometry(mw: Any, obj: SceneObject, geometry: Any) -> Any:
        material_comp = obj.get_component("Material")
        material = (
            MaterialAdapter.to_platform(material_comp)
            if material_comp is not None
            else mw.Material()
        )

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

    @staticmethod
    def _scaled_geometry_to_platform_structure(mw: Any, obj: SceneObject) -> Optional[Any]:
        """Bake a scaled PlatformGeometry primitive into a world-space mesh."""
        import witwin.core as wc

        transform = obj.get_component("Transform")
        if transform is None:
            return None

        structure = MaxwellAdapter._structure_to_platform(mw, obj)
        try:
            world_vertices, faces = structure.geometry.to_mesh()
        except (AttributeError, ImportError, ValueError, RuntimeError):
            return None

        position = np.asarray(_list(transform.position), dtype=np.float32)
        scale = np.asarray(_list(transform.scale), dtype=np.float32)
        rotation_quat = TransformMap.euler_to_quat(transform.rotation)
        w, x, y, z = (float(value) for value in rotation_quat)
        rotation = Rotation.from_quat([x, y, z, w]).as_matrix().astype(np.float32)

        world = np.asarray(world_vertices, dtype=np.float32).reshape(-1, 3)
        local = (world - position) @ rotation
        face_array = np.asarray(faces, dtype=np.int64).reshape(-1, 3)

        geometry = wc.Mesh(local, face_array, position=position, rotation=rotation_quat,
                           scale=scale, recenter=False)
        return MaxwellAdapter._structure_from_geometry(mw, obj, geometry)

    @staticmethod
    def _mesh_to_platform_structure(mw: Any, obj: SceneObject) -> Optional[Any]:
        """Export a plain studio Mesh object as a maxwell Structure.

        User-created primitives/imports often carry Mesh + Material but no
        PlatformGeometry. Match the wt-FDTD voxelizer's behavior by honoring the
        object's full world transform and baking it into a platform mesh.
        """
        import witwin.core as wc

        mesh_arrays = render_mesh_arrays(obj)
        if mesh_arrays is None:
            return None

        vertices, faces = mesh_arrays
        position, rotation_quat, scale = MaxwellAdapter._world_transform_parts(obj)

        geometry = wc.Mesh(vertices, faces, position=position, rotation=rotation_quat,
                           scale=scale, recenter=False)
        return MaxwellAdapter._structure_from_geometry(mw, obj, geometry)

    @staticmethod
    def _world_transform_parts(obj: SceneObject) -> tuple[list[float], list[float], list[float]]:
        world = get_world_transform(obj).astype(np.float64)
        basis = world[:3, :3]
        scale = [float(np.linalg.norm(basis[:, i])) for i in range(3)]
        rotation_matrix = basis.copy()
        for i, axis_scale in enumerate(scale):
            if axis_scale > 1e-12:
                rotation_matrix[:, i] /= axis_scale
        rotation = Rotation.from_matrix(rotation_matrix)
        x, y, z, w = rotation.as_quat()
        return (
            [float(world[0, 3]), float(world[1, 3]), float(world[2, 3])],
            [float(w), float(x), float(y), float(z)],
            scale,
        )
