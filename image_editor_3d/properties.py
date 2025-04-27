import math
import os
from enum import StrEnum

import bmesh
import bpy
import mathutils
import numpy as np
import OpenImageIO as oiio

from . import dobj


class SpecialMapType(StrEnum):
    Opacity = "Opacity"

class ObjType(StrEnum):
    Invalid = "Invalid"
    UvLayout = "UvLayout"
    Layer = "Layer"

class LayerObjType(StrEnum):
    Invalid = "Invalid"
    Basic = "Basic"
    Image = "Image"
    Overlay = "Overlay"

BASIC_MAP_COUNT = 20
SPECIAL_MAP_COUNT = 1
MAP_COUNT = BASIC_MAP_COUNT + SPECIAL_MAP_COUNT

RESOLUTIONS = [
    128,
    256,
    512,
    1024,
    2048,
    4096,
    8192,
]

COLOR_DEPTHS = [
    8,
    16,
]

SUPPORTED_IMAGE_EXTS = [
    ".bmp",
    ".sgi",
    ".rgb",
    ".bw",
    ".png",
    ".jpg",
    ".jpeg",
    ".jp2",
    ".jp2",
    ".j2c",
    ".tga",
    ".cin",
    ".dpx",
    ".exr",
    ".hdr",
    ".tif",
    ".tiff",
]
IMAGE_FILE_FILTER = ";".join([f"*{f}" for f in SUPPORTED_IMAGE_EXTS])

def loop_index(index, length):
    if length == 0:
        return index
    i = index
    while i < 0:
        i += length
    while i >= length:
        i -= length
    return i

def is_image_file_supported(file_path):
    _, ext = os.path.splitext(file_path)
    return ext in SUPPORTED_IMAGE_EXTS

def uv_tile_num_to_coord(num):
    coord = [
        (num - 1001) % 10,
        (num - 1001) // 10,
        0
    ]
    return coord

def uv_tile_coord_to_num(coord):
    num = 1001 + coord[1] * 10 + coord[0]
    return num

def uv_tile_coord_to_location(coord):
    location = mathutils.Vector((
        coord[0] + 0.5,
        coord[1] + 0.5,
        0.0
    ))
    return location

def location_to_uv_tile_coord(location):
    coord = [
        int(location[0]),
        int(location[1])
    ]
    return coord

def get_addon_dir_path():
    return os.path.dirname(__file__)

def get_user_dir_path():
    # for development
    # addon_dir_path = get_addon_dir_path()
    # user_dir_path = os.path.join(addon_dir_path, "..", "temp")
    user_dir_path = bpy.utils.extension_path_user(__package__, path="", create=True)
    return user_dir_path

def create_dummy_image(file_name, size, opacity):
    user_dir_path = get_user_dir_path()
    file_path = os.path.join(user_dir_path, file_name)

    if not os.path.isfile(file_path):
        spec = oiio.ImageSpec(size, size, 4, "float")
        pixels = np.zeros((size, size, 4), np.float64)
        for row in pixels:
            for pixel in row:
                pixel[3] = opacity
        output = oiio.ImageOutput.create(file_path)
        output.open(file_path, spec)
        output.write_image(pixels)
        output.close()

    return file_path

def find_dummy_image_internal(file_name, opacity):
    file_path = create_dummy_image(file_name, 1, opacity)

    for image in bpy.data.images:
        if image.filepath == file_path:
            return image

    dummy_image = bpy.data.images.load(file_path)
    dummy_image.pack()

    return dummy_image

def find_dummy_image_transparent():
    dummy_image = find_dummy_image_internal("dummy_transparent.png", 0.0)
    return dummy_image

def find_dummy_image_opaque():
    dummy_image = find_dummy_image_internal("dummy_opaque.png", 1.0)
    return dummy_image

def find_addon_collection():
    for collection in bpy.context.scene.collection.children:
        if collection.name == "DO_NOT_EDIT":
            return collection
    return None

def get_camera_location():
    for area in bpy.context.screen.areas:
        if area.type != "VIEW_3D":
            continue
        for space in area.spaces:
            if space.type != "VIEW_3D":
                continue
            return space.region_3d.view_matrix.inverted().translation
    return mathutils.Vector()

def get_obj_type(obj):
    obj_type = ObjType.Invalid
    try:
        if "obj_type" in obj:
            obj_type = ObjType(obj["obj_type"])
    except:
        pass
    return obj_type

def set_obj_type(obj, t):
    try:
        obj["obj_type"] = t
    except:
        pass

def find_objs_with_type(t):
    objs = []
    for obj in bpy.context.scene.objects:
        tt = get_obj_type(obj)
        if tt == t:
            objs.append(obj)
    return objs

def get_layer_obj_type(obj):
    layer_obj_type = LayerObjType.Invalid
    try:
        if "layer_obj_type" in obj:
            layer_obj_type = LayerObjType(obj["layer_obj_type"])
    except:
        pass
    return layer_obj_type

def set_layer_obj_type(obj, t):
    try:
        obj["layer_obj_type"] = t
    except:
        pass

def find_layer_objs_with_type(t):
    layer_objs = []
    for layer_obj in bpy.context.scene.objects:
        tt = get_layer_obj_type(layer_obj)
        if tt == t:
            layer_objs.append(layer_obj)
    return layer_objs

def find_sorted_layer_objs():
    layer_objs = find_objs_with_type(ObjType.Layer)
    layer_objs.sort(key=lambda o: o.location.z)
    return layer_objs

def sort_layer_objs(layer_objs):
    i = 0
    for layer_obj in layer_objs:
        layer_obj_type = get_layer_obj_type(layer_obj)
        if layer_obj_type == LayerObjType.Overlay:
            layer_obj.location.z = 490.0
        else:
            layer_obj.location.z = 0.01 * i
            i += 1

def find_intersection_internal(p0, p1, p2):
    val = (p1.x - p0.x) * (p2.y - p0.y) - (p1.y - p0.y) * (p2.x - p0.x)
    return val

def find_intersection(p00, p01, p10, p11):
    val0 = find_intersection_internal(p00, p01, p10)
    val1 = find_intersection_internal(p00, p01, p11)
    val2 = find_intersection_internal(p10, p11, p00)
    val3 = find_intersection_internal(p10, p11, p01)
    if (val0 * val1 > 0.0) or (val2 * val3 > 0.0):
        return None

    det = (p00.x - p01.x) * (p11.y - p10.y) - (p11.x - p10.x) * (p00.y - p01.y)
    if math.isclose(det, 0.0):
        return None

    t = ((p11.y - p10.y) * (p11.x - p01.x) + (p10.x - p11.x) * (p11.y - p01.y)) / det
    intersection = mathutils.Vector((
        t * p00.x + (1.0 - t) * p01.x,
        t * p00.y + (1.0 - t) * p01.y,
        0.0
    ))
    return intersection

def find_closest_point(p0, p1, p):
    diff0 = p - p0
    diff1 = p1 - p0
    diff2 = p0 - p1
    diff3 = p - p1

    closest_point = mathutils.Vector()
    if diff0.dot(diff1) < 0.0:
        closest_point = p0
    elif diff2.dot(diff3) < 0.0:
        closest_point = p1
    else:
        closest_point = p0 + diff1 / diff1.length * diff0.dot(diff1) / diff1.length
    return closest_point

def face_contains_point(vert_coords, point):
    winding_num = 0
    for i in range(len(vert_coords)):
        current_vert_coord = vert_coords[i]
        next_vert_coord = vert_coords[loop_index(i + 1, len(vert_coords))]

        if (current_vert_coord.y <= point.y) and (next_vert_coord.y > point.y):
            t = (point.y - current_vert_coord.y) / (next_vert_coord.y - current_vert_coord.y)
            if point.x < (current_vert_coord.x + (t * (next_vert_coord.x - current_vert_coord.x))):
                winding_num += 1
        elif (current_vert_coord.y > point.y) and (next_vert_coord.y <= point.y):
            t = (point.y - current_vert_coord.y) / (next_vert_coord.y - current_vert_coord.y)
            if point.x < (current_vert_coord.x + (t * (next_vert_coord.x - current_vert_coord.x))):
                winding_num -= 1

    return winding_num != 0

def list_to_enum_property_items(l):
    items = []
    for i in l:
        item = (str(i), str(i), "")
        items.append(item)
    return items

def enum_cls_to_enum_property_items(enum_cls):
    names = [e.name for e in enum_cls]
    items = list_to_enum_property_items(names)
    return items

def create_plane_obj(size):
    half_size = size / 2

    bm = bmesh.new()
    bm.verts.new((-half_size, -half_size, 0.0))
    bm.verts.new((half_size, -half_size, 0.0))
    bm.verts.new((-half_size, half_size, 0.0))
    bm.verts.new((half_size, half_size, 0.0))
    bmesh.ops.contextual_create(bm, geom=bm.verts)

    bm.faces.ensure_lookup_table()
    face = bm.faces[0]

    layer = bm.loops.layers.uv.verify()
    face.loops[0][layer].uv = (1.0, 0.0)
    face.loops[1][layer].uv = (0.0, 0.0)
    face.loops[2][layer].uv = (0.0, 1.0)
    face.loops[3][layer].uv = (1.0, 1.0)

    mesh = bpy.data.meshes.new("Plane")
    bm.to_mesh(mesh)

    obj = bpy.data.objects.new("Plane", mesh)

    return obj

class BasicLayerObjWrapper(object):
    @classmethod
    def create_obj(cls):
        obj = create_plane_obj(1.0)
        set_obj_type(obj, ObjType.Layer)
        set_layer_obj_type(obj, LayerObjType.Basic)

        return obj

    def __init__(self, obj):
        super(BasicLayerObjWrapper, self).__init__()
        self.obj = obj

class ImageObjWrapper(object):
    @classmethod
    def create_obj(cls):
        ie3 = bpy.context.scene.ie3

        obj = create_plane_obj(1.0)
        set_obj_type(obj, ObjType.Layer)
        set_layer_obj_type(obj, LayerObjType.Image)

        dummy_image = find_dummy_image_opaque()
        for map_data in ie3.map_data_list:
            obj[map_data.internal_name] = dummy_image

        material = bpy.data.materials.new("Material")
        material.surface_render_method = "BLENDED"
        material.use_nodes = True

        node_output = material.node_tree.nodes.get("Material Output")
        node_bsdf = material.node_tree.nodes.get("Principled BSDF")
        node_bsdf.inputs[28].default_value = 1.0
        node_math = material.node_tree.nodes.new("ShaderNodeMath")
        node_math.operation = "MULTIPLY"
        node_math.inputs[1].default_value = 1.0
        node_mix = material.node_tree.nodes.new("ShaderNodeMix")
        node_mix.inputs[0].default_value = 0.0
        node_opacity_map = material.node_tree.nodes.new("ShaderNodeTexImage")
        node_opacity_map.name = "Opacity Map"
        node_opacity_map.image = dummy_image
        node_basic_map = material.node_tree.nodes.new("ShaderNodeTexImage")
        node_basic_map.name = "Basic Map"
        node_basic_map.image = dummy_image
        node_mapping = material.node_tree.nodes.new("ShaderNodeMapping")
        node_tex_coord = material.node_tree.nodes.new("ShaderNodeTexCoord")

        material.node_tree.links.clear()
        material.node_tree.links.new(node_bsdf.outputs[0], node_output.inputs[0])
        material.node_tree.links.new(node_math.outputs[0], node_bsdf.inputs[4])
        material.node_tree.links.new(node_mix.outputs[0], node_math.inputs[0])
        material.node_tree.links.new(node_opacity_map.outputs[1], node_mix.inputs[2])
        material.node_tree.links.new(node_opacity_map.outputs[0], node_mix.inputs[3])
        material.node_tree.links.new(node_basic_map.outputs[0], node_bsdf.inputs[27])
        material.node_tree.links.new(node_mapping.outputs[0], node_opacity_map.inputs[0])
        material.node_tree.links.new(node_mapping.outputs[0], node_basic_map.inputs[0])
        material.node_tree.links.new(node_tex_coord.outputs[2], node_mapping.inputs[0])

        obj.data.materials.append(material)

        return obj

    def __init__(self, obj):
        super(ImageObjWrapper, self).__init__()
        self.obj = obj
        material = self.obj.data.materials[0]
        self.__node_math = material.node_tree.nodes.get("Math")
        self.__node_mix = material.node_tree.nodes.get("Mix")
        self.__node_opacity_map = material.node_tree.nodes.get("Opacity Map")
        self.__node_basic_map = material.node_tree.nodes.get("Basic Map")
        self.__node_mapping = material.node_tree.nodes.get("Mapping")

    def update_maps(self, map_file_path_dict):
        for map_internal_name, map_file_path in map_file_path_dict.items():
            if not map_file_path:
                continue
            m = self.obj[map_internal_name]
            if m.filepath == map_file_path:
                continue
            self.obj[map_internal_name] = bpy.data.images.load(map_file_path)

        self.__node_opacity_map.image = self.obj[SpecialMapType.Opacity.name]

    def switch_map(self, map_internal_name):
        self.__node_basic_map.image = self.obj[map_internal_name]

    def get_b_use_grayscale_as_opacity(self):
        return self.__node_mix.inputs[0].default_value > 0.5

    def set_b_use_grayscale_as_opacity(self, val):
        self.__node_mix.inputs[0].default_value = 1.0 if val else 0.0

    def get_mapping_location(self):
        return self.__node_mapping.inputs[1].default_value

    def set_mapping_location(self, val):
        self.__node_mapping.inputs[1].default_value = val

    def get_mapping_rotation(self):
        return mathutils.Vector(self.__node_mapping.inputs[2].default_value) * 180.0 / math.pi

    def set_mapping_rotation(self, val):
        self.__node_mapping.inputs[2].default_value = mathutils.Vector(val) * math.pi / 180.0

    def get_mapping_scale(self):
        return self.__node_mapping.inputs[3].default_value

    def set_mapping_scale(self, val):
        self.__node_mapping.inputs[3].default_value = val

    def get_opacity(self):
        return self.__node_math.inputs[1].default_value

    def set_opacity(self, val):
        self.__node_math.inputs[1].default_value = val

def get_display_map_name_items(self, context):
    ie3 = context.scene.ie3

    items = []
    current_basic_map_data_list = ie3.get_current_basic_map_data_list()
    for basic_map_data in current_basic_map_data_list:
        display_name = basic_map_data.get_display_name()
        item = (basic_map_data.internal_name, display_name, "")
        items.append(item)

    return items

def display_map_name_changed(self, context):
    ie3 = context.scene.ie3

    image_objs = find_layer_objs_with_type(LayerObjType.Image)
    image_obj_wrappers = [ImageObjWrapper(o) for o in image_objs]
    for image_obj_wrapper in image_obj_wrappers:
        image_obj_wrapper.switch_map(ie3.display_map_name)

def basic_map_count_changed(self, context):
    ie3 = context.scene.ie3

    if not ie3.display_map_name:
        ie3.display_map_name = "BasicMap0"

def mapping_property_changed(self, context):
    ie3 = context.scene.ie3

    layer_obj_type = get_layer_obj_type(context.active_object)
    if layer_obj_type != LayerObjType.Image:
        return

    image_obj_wrapper = ImageObjWrapper(context.active_object)
    image_obj_wrapper.mapping_location = ie3.mapping_location
    image_obj_wrapper.mapping_rotation = ie3.mapping_rotation
    image_obj_wrapper.mapping_scale = ie3.mapping_scale

def image_obj_property_changed(self, context):
    ie3 = context.scene.ie3
    if ie3.b_is_initializing_image_obj_properties:
        return

    layer_obj_type = get_layer_obj_type(context.active_object)
    if layer_obj_type != LayerObjType.Image:
        return

    image_obj_wrapper = ImageObjWrapper(context.active_object)

    map_file_path_dict = {}
    for map_data in ie3.map_data_list:
        map_file_path_dict[map_data.internal_name] = map_data.file_path
    image_obj_wrapper.update_maps(map_file_path_dict)

    image_obj_wrapper.set_b_use_grayscale_as_opacity(ie3.b_use_grayscale_as_opacity)
    image_obj_wrapper.set_mapping_location(ie3.mapping_location)
    image_obj_wrapper.set_mapping_rotation(ie3.mapping_rotation)
    image_obj_wrapper.set_mapping_scale(ie3.mapping_scale)
    image_obj_wrapper.set_opacity(ie3.opacity)

    image_obj_wrapper.switch_map(ie3.display_map_name)

def show_overlay_changed(self, context):
    ie3 = context.scene.ie3

    overlay_objs = find_layer_objs_with_type(LayerObjType.Overlay)
    for overlay_obj in overlay_objs:
        overlay_obj.hide_viewport = not ie3.b_show_overlay

def overlay_opacity_changed(self, context):
    ie3 = context.scene.ie3

    overlay_objs = find_layer_objs_with_type(LayerObjType.Overlay)
    for overlay_obj in overlay_objs:
        overlay_obj.color = [1.0, 1.0, 1.0, ie3.overlay_opacity]

class UvTileData(bpy.types.PropertyGroup):
    num: bpy.props.IntProperty(name="Num")
    coord: bpy.props.IntVectorProperty(name="Coord")

class MapType(StrEnum):
    Basic = "Basic"
    Special = "Special"

class MapData(bpy.types.PropertyGroup):
    type: bpy.props.EnumProperty(name="Type", items=enum_cls_to_enum_property_items(MapType))
    internal_name: bpy.props.StringProperty(name="Internal Name")
    display_name: bpy.props.StringProperty(name="Display Name")
    default_name: bpy.props.StringProperty(name="Default Name")
    file_path: bpy.props.StringProperty(name="File Path", update=image_obj_property_changed)
    color_depth: bpy.props.EnumProperty(name="Color Depth", items=list_to_enum_property_items(COLOR_DEPTHS))
    file_name_keywords: bpy.props.StringProperty(name="File Name Keywords")

    def get_type(self):
        t = MapType(self.type)
        return t

    def get_display_name(self):
        if self.display_name:
            return self.display_name
        return self.default_name

class SceneData(bpy.types.PropertyGroup):
    b_is_editor_scene: bpy.props.BoolProperty(name="Is editor scene")
    b_is_initializing_image_obj_properties: bpy.props.BoolProperty(name="Is initializing image obj properties")
    resolution: bpy.props.EnumProperty(name="Resolution", items=list_to_enum_property_items(RESOLUTIONS), default=str(1024))
    basic_map_count: bpy.props.IntProperty(name="Basic Map Count", min=1, max=BASIC_MAP_COUNT, default=1)
    display_map_name: bpy.props.EnumProperty(name="Display Map Name", items=get_display_map_name_items, update=display_map_name_changed)
    mapping_location: bpy.props.FloatVectorProperty(name="Mapping Location", update=image_obj_property_changed)
    mapping_rotation: bpy.props.FloatVectorProperty(name="Mapping Rotation", update=image_obj_property_changed)
    mapping_scale: bpy.props.FloatVectorProperty(name="Mapping Scale", update=image_obj_property_changed)
    opacity: bpy.props.FloatProperty(name="Opacity", min=0.0, max=1.0, update=image_obj_property_changed)
    b_show_overlay: bpy.props.BoolProperty(name="Show overlay", default=True, update=show_overlay_changed)
    overlay_opacity: bpy.props.FloatProperty(name="Overlay Opacity", min=0.0, max=1.0, default=0.5, update=overlay_opacity_changed)
    b_use_grayscale_as_opacity: bpy.props.BoolProperty(name="Use grayscale as opacity", update=image_obj_property_changed)
    uv_tile_data_list: bpy.props.CollectionProperty(type=UvTileData, name="UV Tile Data List")
    map_data_list: bpy.props.CollectionProperty(type=MapData, name="Map Data List")
    map_file_name: bpy.props.StringProperty(name="Map File Name")

    def get_basic_map_data_list(self):
        basic_map_data_list = [d for d in self.map_data_list if d.get_type() == MapType.Basic]
        return basic_map_data_list

    def get_special_map_data_list(self):
        special_map_data_list = [d for d in self.map_data_list if d.get_type() == MapType.Special]
        return special_map_data_list

    def get_current_basic_map_data_list(self):
        basic_map_data_list = self.get_basic_map_data_list()
        current_basic_map_data_list = basic_map_data_list[:self.basic_map_count]
        return current_basic_map_data_list

    def get_current_map_data_list(self):
        current_basic_map_data_list = self.get_current_basic_map_data_list()
        special_map_data_list = self.get_special_map_data_list()
        current_map_data_list = list(current_basic_map_data_list) + list(special_map_data_list)
        return current_map_data_list

class MapSettingGroup(dobj.Dobj):
    def __init__(self):
        self.internal_name = ""
        self.display_name = ""
        self.color_depth = ""
        self.file_name_keywords = ""

    def to_dict(self):
        d = {
            "internal_name": self.internal_name,
            "display_name": self.display_name,
            "color_depth": self.color_depth,
            "file_name_keywords": self.file_name_keywords,
        }
        return d

    @classmethod
    def from_dict(cls, d):
        instance = cls()
        instance.internal_name = d["internal_name"]
        instance.display_name = d["display_name"]
        instance.color_depth = d["color_depth"]
        instance.file_name_keywords = d["file_name_keywords"]
        return instance

class SceneSettingGroup(dobj.Dobj):
    def __init__(self):
        self.map_file_name = ""
        self.resolution = ""
        self.basic_map_count = 0
        self.map_setting_groups = []

    def to_dict(self):
        d = {
            "map_file_name": self.map_file_name,
            "resolution": self.resolution,
            "basic_map_count": self.basic_map_count,
            "map_setting_groups": dobj.dobjs_to_dicts(self.map_setting_groups),
        }
        return d

    @classmethod
    def from_dict(cls, d):
        instance = cls()
        instance.map_file_name = d["map_file_name"]
        instance.resolution = d["resolution"]
        instance.basic_map_count = d["basic_map_count"]
        instance.map_setting_groups = dobj.dicts_to_dobjs(d["map_setting_groups"], MapSettingGroup)
        return instance

clss = [
    MapData,
    UvTileData,
    SceneData,
]
