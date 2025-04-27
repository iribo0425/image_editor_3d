import glob
import os
import re
import sys
from enum import StrEnum

import bmesh
import bpy
import mathutils
import OpenImageIO as oiio

from . import dobj, properties


def active_obj_changed():
    ie3 = bpy.context.scene.ie3
    ie3.b_is_initializing_image_obj_properties = True

    layer_obj_type = properties.get_layer_obj_type(bpy.context.active_object)
    if layer_obj_type != properties.LayerObjType.Image:
        return

    image_obj_wrapper = properties.ImageObjWrapper(bpy.context.active_object)

    for map_data in ie3.map_data_list:
        m = image_obj_wrapper.obj[map_data.internal_name]
        map_data.file_path = m.filepath

    ie3.b_use_grayscale_as_opacity = image_obj_wrapper.get_b_use_grayscale_as_opacity()
    ie3.mapping_location = image_obj_wrapper.get_mapping_location()
    ie3.mapping_rotation = image_obj_wrapper.get_mapping_rotation()
    ie3.mapping_scale = image_obj_wrapper.get_mapping_scale()
    ie3.opacity = image_obj_wrapper.get_opacity()

    uv_layout_objs = properties.find_objs_with_type(properties.ObjType.UvLayout)
    if uv_layout_objs:
        uv_layout_obj = uv_layout_objs[0]
        uv_layout_obj.location.z = image_obj_wrapper.obj.location.z

    ie3.b_is_initializing_image_obj_properties = False

class OT_StartEditing(bpy.types.Operator):
    bl_idname = "scene.start_editing"
    bl_label = "Start editing"

    def execute(self, context):
        user_dir_path = properties.get_user_dir_path()
        # self.report({"INFO"}, f"User Dir Path: {user_dir_path}")

        uv_bm = bmesh.new()

        if context.active_object and (context.active_object.type == "MESH"):
            uv_layout_file_path = os.path.join(user_dir_path, "UvLayout.png")
            bpy.ops.uv.export_layout(filepath=uv_layout_file_path, export_tiles="UDIM")

            bm = bmesh.new()
            bm.from_mesh(context.active_object.data)

            for face in bm.faces:
                uv_verts = []
                for loop in face.loops:
                    loop_uv = loop[bm.loops.layers.uv.active]
                    uv_vert = uv_bm.verts.new(loop_uv.uv.to_3d())
                    uv_verts.append(uv_vert)
                uv_bm.faces.new(uv_verts)

            bm.free()

        new_scene = bpy.data.scenes.new("Image Editor 3D")
        new_scene.ie3.b_is_editor_scene = True
        new_scene.render.film_transparent = True
        new_scene.view_settings.view_transform = "Standard"
        bpy.context.window.scene = new_scene
        bpy.context.space_data.shading.type = "RENDERED"
        bpy.ops.view3d.view_axis(type="TOP")

        addon_collection = bpy.data.collections.new("DO_NOT_EDIT")
        bpy.context.collection.children.link(addon_collection)
        addon_collection.hide_render = True

        for i in range(properties.BASIC_MAP_COUNT):
            map_data = new_scene.ie3.map_data_list.add()
            map_data.type = properties.MapType.Basic.name
            map_data.internal_name = f"BasicMap{i}"
            map_data.default_name = f"Map{i + 1}"

        for special_map_type in properties.SpecialMapType:
            map_data = new_scene.ie3.map_data_list.add()
            map_data.type = properties.MapType.Special.name
            map_data.internal_name = special_map_type.name
            map_data.default_name = special_map_type.name

        re_pattern = re.compile(r"UvLayout\.(\d+)\.png")
        uv_layout_file_paths = glob.glob(f"{user_dir_path}/UvLayout.*.png")
        if not uv_layout_file_paths:
            uv_layout_file_paths = [
                properties.create_dummy_image("UvLayout.1001.png", 1024, 0.0)
            ]

        for uv_layout_file_path in uv_layout_file_paths:
            uv_layout_file_name = os.path.basename(uv_layout_file_path)
            search_result = re_pattern.search(uv_layout_file_name)
            uv_tile_num = int(search_result.group(1))
            uv_tile_coord = properties.uv_tile_num_to_coord(uv_tile_num)

            image_buf = oiio.ImageBuf(uv_layout_file_path)
            image_spec = image_buf.spec()
            for i in range(3):
                oiio.ImageBufAlgo.render_box(image_buf, i, i, image_spec.width - i - 1, image_spec.height - i - 1, (1.0, 1.0, 1.0, 1.0))
            overlay_file_path = os.path.join(user_dir_path, f"Overlay_{uv_tile_num}.png")
            image_buf.write(overlay_file_path)
            overlay = bpy.data.images.load(overlay_file_path)
            overlay.pack()
            os.remove(overlay_file_path)

            overlay_obj = bpy.data.objects.new(f"Overlay_{uv_tile_num}", None)
            addon_collection.objects.link(overlay_obj)
            overlay_obj.empty_display_type = "IMAGE"
            overlay_obj.data = overlay
            overlay_obj.empty_image_offset = [0.0, 0.0]
            overlay_obj.use_empty_image_alpha = True
            overlay_obj.color = [1.0, 1.0, 1.0, new_scene.ie3.overlay_opacity]
            overlay_obj.hide_select = True
            overlay_obj.hide_render = True
            overlay_obj.location = properties.uv_tile_coord_to_location(uv_tile_coord) - mathutils.Vector((0.5, 0.5, 0.0))
            properties.set_obj_type(overlay_obj, properties.ObjType.Layer)
            properties.set_layer_obj_type(overlay_obj, properties.LayerObjType.Overlay)

            uv_tile_data = new_scene.ie3.uv_tile_data_list.add()
            uv_tile_data.num = uv_tile_num
            uv_tile_data.coord = uv_tile_coord

            uv_tile_center = properties.uv_tile_coord_to_location(uv_tile_coord)
            center_to_corner = [
                mathutils.Vector((-0.5, -0.5, 0.0)),
                mathutils.Vector((0.5, -0.5, 0.0)),
                mathutils.Vector((0.5, 0.5, 0.0)),
                mathutils.Vector((-0.5, 0.5, 0.0)),
            ]
            uv_verts = []
            for to_corner in center_to_corner:
                uv_tile_corner = uv_tile_center + to_corner
                uv_vert = uv_bm.verts.new(uv_tile_corner)
                uv_verts.append(uv_vert)

            for i in range(len(uv_verts)):
                current_vert = uv_verts[i]
                next_vert = uv_verts[(properties.loop_index(i + 1, len(uv_verts)))]
                uv_bm.edges.new([current_vert, next_vert])

        uv_layout_mesh = bpy.data.meshes.new("UvLayout")
        uv_bm.to_mesh(uv_layout_mesh)
        uv_bm.free()

        uv_layout_obj = bpy.data.objects.new("UvLayout", uv_layout_mesh)
        addon_collection.objects.link(uv_layout_obj)
        properties.set_obj_type(uv_layout_obj, properties.ObjType.UvLayout)
        uv_layout_obj.hide_select = True
        uv_layout_obj.hide_render = True

        material = bpy.data.materials.new("Material")
        material.use_nodes = True
        node_bsdf = material.node_tree.nodes.get("Principled BSDF")
        node_bsdf.inputs[4].default_value = 0.0
        uv_layout_obj.data.materials.append(material)

        layer_objs = properties.find_objs_with_type(properties.ObjType.Layer)
        properties.sort_layer_objs(layer_objs)

        for uv_layout_file_path in uv_layout_file_paths:
            os.remove(uv_layout_file_path)

        bpy.msgbus.clear_by_owner("ie3")
        bpy.msgbus.subscribe_rna(
            key=(bpy.types.LayerObjects, "active"),
            owner="ie3",
            args=(),
            notify=active_obj_changed
        )

        return {"FINISHED"}

class OT_SaveSceneSettingGroup(bpy.types.Operator):
    bl_idname = "object.save_scene_setting_group"
    bl_label = "Save scene setting group"

    filepath: bpy.props.StringProperty(options={"HIDDEN"})
    filename: bpy.props.StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        self.filename = "SceneSetting.json"
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def execute(self, context):
        ie3 = context.scene.ie3

        _, ext = os.path.splitext(self.filepath)
        if ext != ".json":
            self.report({"ERROR"}, "The settings file must be in JSON format.")
            return {"FINISHED"}

        scene_setting_group = properties.SceneSettingGroup()
        scene_setting_group.map_file_name = ie3.map_file_name
        scene_setting_group.resolution = ie3.resolution
        scene_setting_group.basic_map_count = ie3.basic_map_count

        for map_data in ie3.map_data_list:
            map_setting_group = properties.MapSettingGroup()
            map_setting_group.internal_name = map_data.internal_name
            map_setting_group.file_name_keywords = map_data.file_name_keywords
            t = map_data.get_type()
            if t == properties.MapType.Basic:
                map_setting_group.display_name = map_data.display_name
                map_setting_group.color_depth = map_data.color_depth
            elif t == properties.MapType.Special:
                pass
            scene_setting_group.map_setting_groups.append(map_setting_group)

        error = dobj.write_dobj(scene_setting_group, self.filepath)
        if error:
            self.report({"ERROR"}, error)
            return {"FINISHED"}

        return {"FINISHED"}

class OT_LoadSceneSettingGroup(bpy.types.Operator):
    bl_idname = "object.load_scene_setting_group"
    bl_label = "Load scene setting group"

    filepath: bpy.props.StringProperty(options={"HIDDEN"})
    filter_glob: bpy.props.StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def execute(self, context):
        ie3 = context.scene.ie3

        scene_setting_group, error = dobj.read_dobj(self.filepath, properties.SceneSettingGroup)
        if error:
            self.report({"ERROR"}, error)
            return {"FINISHED"}

        ie3.map_file_name = scene_setting_group.map_file_name
        ie3.resolution = scene_setting_group.resolution
        ie3.basic_map_count = scene_setting_group.basic_map_count

        for map_setting_group in scene_setting_group.map_setting_groups:
            for map_data in ie3.map_data_list:
                if map_data.internal_name != map_setting_group.internal_name:
                    continue

                map_data.file_name_keywords = map_setting_group.file_name_keywords

                t = map_data.get_type()
                if t == properties.MapType.Basic:
                    map_data.display_name = map_setting_group.display_name
                    map_data.color_depth = map_setting_group.color_depth
                    pass
                elif t == properties.MapType.Special:
                    pass

        return {"FINISHED"}

class OT_CreateImageObj(bpy.types.Operator):
    bl_idname = "object.create_image_obj"
    bl_label = "Create image obj"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        image_obj = properties.ImageObjWrapper.create_obj()
        image_obj_wrapper = properties.ImageObjWrapper(image_obj)
        context.scene.collection.objects.link(image_obj_wrapper.obj)
        image_obj_wrapper.obj.name = f"Image"
        # image_obj_wrapper.obj.scale = mathutils.Vector((0.5, 0.5, 1.0))

        camera_location = properties.get_camera_location()
        uv_tile_coord = properties.location_to_uv_tile_coord(camera_location)
        image_obj_wrapper.obj.location = properties.uv_tile_coord_to_location(uv_tile_coord)

        sorted_layer_objs = properties.find_sorted_layer_objs()
        sorted_layer_objs.append(image_obj_wrapper.obj)
        properties.sort_layer_objs(sorted_layer_objs)

        context.view_layer.objects.active = image_obj_wrapper.obj
        for obj in context.scene.collection.all_objects:
            obj.select_set(obj == image_obj_wrapper.obj)

        return {"FINISHED"}

class OT_CreateBasicLayerObj(bpy.types.Operator):
    bl_idname = "object.create_basic_layer_obj"
    bl_label = "Create basic layer obj"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        basic_layer_obj = properties.BasicLayerObjWrapper.create_obj()
        basic_layer_obj_wrapper = properties.BasicLayerObjWrapper(basic_layer_obj)
        context.scene.collection.objects.link(basic_layer_obj_wrapper.obj)
        basic_layer_obj_wrapper.obj.name = f"Layer"
        # basic_layer_obj_wrapper.obj.scale = mathutils.Vector((0.5, 0.5, 1.0))

        camera_location = properties.get_camera_location()
        uv_tile_coord = properties.location_to_uv_tile_coord(camera_location)
        basic_layer_obj_wrapper.obj.location = properties.uv_tile_coord_to_location(uv_tile_coord)

        sorted_layer_objs = properties.find_sorted_layer_objs()
        sorted_layer_objs.append(basic_layer_obj_wrapper.obj)
        properties.sort_layer_objs(sorted_layer_objs)

        context.view_layer.objects.active = basic_layer_obj_wrapper.obj
        for obj in context.scene.collection.all_objects:
            obj.select_set(obj == basic_layer_obj_wrapper.obj)

        return {"FINISHED"}

class OT_DuplicateLayerObj(bpy.types.Operator):
    bl_idname = "object.duplicate_layer_obj"
    bl_label = "Duplicate layer obj"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        obj_type = properties.get_obj_type(context.active_object)
        if obj_type != properties.ObjType.Layer:
            return {"FINISHED"}

        layer_obj_type = properties.get_layer_obj_type(context.active_object)
        if layer_obj_type == properties.LayerObjType.Overlay:
            return {"FINISHED"}

        for obj in context.scene.objects:
            obj.select_set(obj == context.active_object)
        bpy.ops.object.duplicate()

        if layer_obj_type == properties.LayerObjType.Image:
            context.active_object.data.materials[0] = context.active_object.data.materials[0].copy()

        sorted_layer_objs = properties.find_sorted_layer_objs()
        sorted_layer_objs.append(context.active_object)
        properties.sort_layer_objs(sorted_layer_objs)

        return {"FINISHED"}

class OT_SelectImageObjMap(bpy.types.Operator):
    bl_idname = "wm.select_image_obj_map"
    bl_label = "Select image obj map"
    bl_options = {"REGISTER", "UNDO"}

    map_data_index: bpy.props.IntProperty(options={"HIDDEN"})
    filepath: bpy.props.StringProperty(options={"HIDDEN"})
    filter_glob: bpy.props.StringProperty(default=properties.IMAGE_FILE_FILTER, options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        ie3 = context.scene.ie3

        current_map_data_list = ie3.get_current_map_data_list()
        map_data = current_map_data_list[self.map_data_index]
        setattr(map_data, "file_path", self.filepath)

        return {"FINISHED"}

class OT_SelectImageObjMapsWithKeywords(bpy.types.Operator):
    bl_idname = "wm.select_image_obj_maps_by_keywords"
    bl_label = "Select image obj maps by keywords"
    bl_options = {"REGISTER", "UNDO"}

    directory: bpy.props.StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def execute(self, context):
        ie3 = context.scene.ie3

        file_paths = glob.glob(f"{self.directory}\*")

        current_map_data_list = ie3.get_current_map_data_list()
        for map_data in current_map_data_list:
            file_name_keywords = map_data.file_name_keywords.split(",")

            for file_path in file_paths:
                if not properties.is_image_file_supported(file_path):
                    continue

                file_name = os.path.basename(file_path)
                for file_name_keyword in file_name_keywords:
                    if file_name_keyword and (file_name_keyword in file_name):
                        map_data.file_path = file_path

        return {"FINISHED"}

class OT_SnapVertToClosestUvVert(bpy.types.Operator):
    bl_idname = "mesh.snap_vert_to_closest_uv_vert"
    bl_label = "Snap vert to closest uv vert"
    bl_options = {"REGISTER", "UNDO"}

    offset_amount: bpy.props.FloatProperty("Offset Amount", default=0.0)

    class VertData:
        def __init__(self):
            self.index = 0
            self.target_location = mathutils.Vector()
            self.offset_direction = mathutils.Vector()

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def invoke(self, context, event):
        self.offset_amount = 0.0
        self.vert_data_list = []

        uv_layout_objs = properties.find_objs_with_type(properties.ObjType.UvLayout)
        if not uv_layout_objs:
            return {"FINISHED"}
        uv_layout_obj = uv_layout_objs[0]
        uv_bm = bmesh.new()
        uv_bm.from_mesh(uv_layout_obj.data)

        bm = bmesh.from_edit_mesh(context.edit_object.data)

        for vert in bm.verts:
            if not vert.select:
                continue

            vert_data = self.VertData()
            vert_data.index = vert.index

            vert_coord = context.edit_object.matrix_world @ vert.co

            min_distance = sys.float_info.max
            b_is_found = False
            for uv_face in uv_bm.faces:
                uv_vert_coords = []
                for uv_loop in uv_face.loops:
                    uv_vert_coords.append(uv_loop.vert.co)

                if not properties.face_contains_point(uv_vert_coords, vert_coord):
                    continue

                for i, uv_vert_coord in enumerate(uv_vert_coords):
                    uv_vert_coord.z = vert_coord.z
                    distance = (uv_vert_coord - vert_coord).length
                    if distance < min_distance:
                        min_distance = distance
                        vert_data.target_location = uv_vert_coord
                        b_is_found = True

                        prev_vert_coord = uv_vert_coords[properties.loop_index(i - 1, len(uv_vert_coords))]
                        prev_vert_coord.z = vert_coord.z
                        next_vert_coord = uv_vert_coords[properties.loop_index(i + 1, len(uv_vert_coords))]
                        next_vert_coord.z = vert_coord.z
                        edge0 = (prev_vert_coord - uv_vert_coord).normalized()
                        edge1 = (next_vert_coord - uv_vert_coord).normalized()
                        vert_data.offset_direction = (edge0 + edge1).normalized()
                        if not properties.face_contains_point(uv_vert_coords, uv_vert_coord + vert_data.offset_direction * 0.001):
                            vert_data.offset_direction.negate()

            if not b_is_found:
                for uv_face in uv_bm.faces:
                    for uv_loop in uv_face.loops:
                        uv_vert_coord = uv_loop.vert.co
                        uv_vert_coord.z = vert_coord.z
                        distance = (uv_vert_coord - vert_coord).length
                        if distance < min_distance:
                            min_distance = distance
                            vert_data.target_location = uv_vert_coord
                            b_is_found = True

            self.vert_data_list.append(vert_data)

        return self.execute(context)

    def execute(self, context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)

        for vert in bm.verts:
            vert_data = None
            for data in self.vert_data_list:
                if data.index == vert.index:
                    vert_data = data
                    break
            if not vert_data:
                continue

            co = vert_data.target_location + vert_data.offset_direction * self.offset_amount
            vert.co = context.edit_object.matrix_world.inverted() @ co

        bmesh.update_edit_mesh(context.edit_object.data)

        return {"FINISHED"}

class OT_SnapVertToUvEdge(bpy.types.Operator):
    bl_idname = "mesh.snap_vert_to_uv_edge"
    bl_label = "Snap vert to uv edge"
    bl_options = {"REGISTER", "UNDO"}

    class Direction(StrEnum):
        XPlus = "XPlus"
        XMinus = "XMinus"
        YPlus = "YPlus"
        YMinus = "YMinus"

    direction: bpy.props.EnumProperty(items=properties.enum_cls_to_enum_property_items(Direction), options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        uv_layout_objs = properties.find_objs_with_type(properties.ObjType.UvLayout)
        if not uv_layout_objs:
            return {"FINISHED"}
        uv_layout_obj = uv_layout_objs[0]
        uv_bm = bmesh.new()
        uv_bm.from_mesh(uv_layout_obj.data)

        bm = bmesh.from_edit_mesh(context.edit_object.data)

        for vert in bm.verts:
            if not vert.select:
                continue

            p00 = context.edit_object.matrix_world @ vert.co
            p01 = p00.copy()
            direction = self.Direction(self.direction)
            if direction == self.Direction.XMinus:
                p00 += mathutils.Vector((-0.001, 0.0, 0.0))
                p01 += mathutils.Vector((-1000.0, 0.0, 0.0))
            elif direction == self.Direction.XPlus:
                p00 += mathutils.Vector((0.001, 0.0, 0.0))
                p01 += mathutils.Vector((1000.0, 0.0, 0.0))
            if direction == self.Direction.YMinus:
                p00 += mathutils.Vector((0.0, -0.001, 0.0))
                p01 += mathutils.Vector((0.0, -1000.0, 0.0))
            elif direction == self.Direction.YPlus:
                p00 += mathutils.Vector((0.0, 0.001, 0.0))
                p01 += mathutils.Vector((0.0, 1000.0, 0.0))

            min_distance = sys.float_info.max
            target_location = mathutils.Vector()
            b_is_found = False
            for uv_edge in uv_bm.edges:
                p10 = uv_edge.verts[0].co
                p11 = uv_edge.verts[1].co

                intersection = properties.find_intersection(p00, p01, p10, p11)
                if intersection:
                    distance = (intersection - p00).length
                    if distance < min_distance:
                        min_distance = distance
                        target_location = intersection
                        target_location.z = p00.z
                        b_is_found = True

            if b_is_found:
                vert.co = context.edit_object.matrix_world.inverted() @ target_location

        bmesh.update_edit_mesh(context.edit_object.data)

        return {"FINISHED"}

class OT_SnapVertToClosestUvEdge(bpy.types.Operator):
    bl_idname = "mesh.snap_vert_to_closest_uv_edge"
    bl_label = "Snap vert to closest uv edge"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        uv_layout_objs = properties.find_objs_with_type(properties.ObjType.UvLayout)
        if not uv_layout_objs:
            return {"FINISHED"}
        uv_layout_obj = uv_layout_objs[0]
        uv_bm = bmesh.new()
        uv_bm.from_mesh(uv_layout_obj.data)

        bm = bmesh.from_edit_mesh(context.edit_object.data)

        for vert in bm.verts:
            if not vert.select:
                continue

            vert_coord = context.edit_object.matrix_world @ vert.co

            min_distance = sys.float_info.max
            target_location = mathutils.Vector()
            b_is_found = False
            for uv_edge in uv_bm.edges:
                p0 = uv_edge.verts[0].co
                p1 = uv_edge.verts[1].co

                closest_point = properties.find_closest_point(p0, p1, vert_coord)
                distance = (closest_point - vert_coord).length
                if distance < min_distance:
                    min_distance = distance
                    target_location = closest_point
                    target_location.z = vert_coord.z
                    b_is_found = True

            if b_is_found:
                vert.co = context.edit_object.matrix_world.inverted() @ target_location

        bmesh.update_edit_mesh(context.edit_object.data)

        return {"FINISHED"}

class OT_AlignVerts(bpy.types.Operator):
    bl_idname = "mesh.align_verts"
    bl_label = "Align verts"
    bl_options = {"REGISTER", "UNDO"}

    class VertData:
        def __init__(self):
            self.vert = None
            self.connected_vert_data_list = []
            self.b_is_visited = False

    @classmethod
    def poll(cls, context):
        return context.mode == "EDIT_MESH"

    def execute(self, context):
        bm = bmesh.from_edit_mesh(context.edit_object.data)

        vert_data_list = []
        for vert in bm.verts:
            if vert.select:
                vert_data = self.VertData()
                vert_data.vert = vert
                vert_data_list.append(vert_data)

        for vert_data in vert_data_list:
            b_is_found = False
            for edge in vert_data.vert.link_edges:
                other_vert = edge.other_vert(vert_data.vert)

                for vd in vert_data_list:
                    if vd.vert == other_vert:
                        vert_data.connected_vert_data_list.append(vd)
                        b_is_found = True
                        break

            if not b_is_found:
                self.report({"ERROR"}, "Please select the vertices correctly.")
                return {"FINISHED"}

        current_vert_data = None
        end_count = 0
        for vert_data in vert_data_list:
            if len(vert_data.connected_vert_data_list) == 1:
                current_vert_data = vert_data
                end_count += 1

        if end_count != 2:
            self.report({"ERROR"}, "Please select the vertices correctly.")
            return {"FINISHED"}

        ordered_vert_data_list = [current_vert_data]
        current_vert_data.b_is_visited = True
        while True:
            for connected_vert_data in current_vert_data.connected_vert_data_list:
                if not connected_vert_data.b_is_visited:
                    connected_vert_data.b_is_visited = True
                    ordered_vert_data_list.append(connected_vert_data)
                    current_vert_data = connected_vert_data
                    break

            if len(current_vert_data.connected_vert_data_list) == 1:
                break

        start_location = ordered_vert_data_list[0].vert.co
        end_location = ordered_vert_data_list[len(ordered_vert_data_list) - 1].vert.co

        for i, ordered_vert_data in enumerate(ordered_vert_data_list):
            ordered_vert_data.vert.co = start_location.lerp(end_location, 1.0 / (len(ordered_vert_data_list) - 1) * i)

        bmesh.update_edit_mesh(context.edit_object.data)

        return {"FINISHED"}

class OT_MoveLayerObj(bpy.types.Operator):
    bl_idname = "object.move_layer_obj"
    bl_label = "Move layer obj"
    bl_options = {"REGISTER", "UNDO"}

    class Target(StrEnum):
        Up = "Up"
        Down = "Down"
        Top = "Top"
        Bottom = "Bottom"

    target: bpy.props.EnumProperty(items=properties.enum_cls_to_enum_property_items(Target), options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT"

    def execute(self, context):
        obj_type = properties.get_obj_type(context.active_object)
        if obj_type != properties.ObjType.Layer:
            return {"FINISHED"}

        sorted_layer_objs = properties.find_sorted_layer_objs()
        layer_obj_index = sorted_layer_objs.index(context.active_object)

        other_obj_index = 0
        target = self.Target(self.target)
        if target == self.Target.Up:
            other_obj_index = layer_obj_index + 1
        elif target == self.Target.Down:
            other_obj_index = layer_obj_index - 1
        elif target == self.Target.Top:
            other_obj_index = len(sorted_layer_objs) - 1
        elif target == self.Target.Bottom:
            other_obj_index = 0
        else:
            return {"FINISHED"}

        if (other_obj_index < 0)\
            or (other_obj_index >= len(sorted_layer_objs)):
            return {"FINISHED"}

        sorted_layer_objs[layer_obj_index] = sorted_layer_objs[other_obj_index]
        sorted_layer_objs[other_obj_index] = context.active_object
        properties.sort_layer_objs(sorted_layer_objs)

        return {"FINISHED"}

class OT_ExportMaps(bpy.types.Operator):
    bl_idname = "render.export_maps"
    bl_label = "Export maps"

    directory: bpy.props.StringProperty(options={"HIDDEN"})

    def invoke(self, context, event):
        ie3 = context.scene.ie3

        if not ie3.map_file_name:
            self.report({"ERROR"}, "Please enter \"Scene Settings > File Name\".")
            return {"CANCELLED"}

        context.window_manager.fileselect_add(self)

        return {"RUNNING_MODAL"}

    def execute(self, context):
        ie3 = context.scene.ie3

        camera = bpy.data.cameras.new("Camera")
        camera.type = "ORTHO"
        camera.ortho_scale = 1.0
        camera_obj = bpy.data.objects.new("Camera", camera)
        context.scene.collection.objects.link(camera_obj)
        context.scene.camera = camera_obj

        context.scene.render.resolution_x = int(ie3.resolution)
        context.scene.render.resolution_y = int(ie3.resolution)

        image_objs = properties.find_layer_objs_with_type(properties.LayerObjType.Image)
        image_obj_wrappers = [properties.ImageObjWrapper(o) for o in image_objs]

        current_basic_map_data_list = ie3.get_current_basic_map_data_list()

        for uv_tile_data in ie3.uv_tile_data_list:
            camera_obj.location = properties.uv_tile_coord_to_location(uv_tile_data.coord)
            camera_obj.location.z = 500.0

            for basic_map_data in current_basic_map_data_list:
                display_name = basic_map_data.get_display_name()
                context.scene.render.filepath = os.path.join(self.directory, f"{ie3.map_file_name}_{uv_tile_data.num}_{display_name}.png")

                for image_obj_wrapper in image_obj_wrappers:
                    image_obj_wrapper.switch_map(basic_map_data.internal_name)

                context.scene.render.image_settings.color_depth = basic_map_data.color_depth
                bpy.ops.render.render(write_still=True)

        bpy.data.objects.remove(camera_obj)
        bpy.data.cameras.remove(camera)

        return {"FINISHED"}

clss = [
    OT_StartEditing,
    OT_SaveSceneSettingGroup,
    OT_LoadSceneSettingGroup,
    OT_CreateImageObj,
    OT_CreateBasicLayerObj,
    OT_DuplicateLayerObj,
    OT_SelectImageObjMap,
    OT_SelectImageObjMapsWithKeywords,
    OT_SnapVertToClosestUvVert,
    OT_SnapVertToUvEdge,
    OT_SnapVertToClosestUvEdge,
    OT_AlignVerts,
    OT_MoveLayerObj,
    OT_ExportMaps,
]
