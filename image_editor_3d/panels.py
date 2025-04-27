import bpy

from . import operators, properties


class PT_Main(bpy.types.Panel):
    bl_idname = "IE3_PT_Main"
    bl_label = "Image Editor 3D"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Tool"

    def draw(self, context):
        ie3 = context.scene.ie3
        layout = self.layout

        if not ie3.b_is_editor_scene:
            self.layout.operator(operators.OT_StartEditing.bl_idname)
            return

        header_scene_settings, panel_scene_settings = layout.panel("scene_settings", default_closed=True)
        header_scene_settings.label(text="Scene Settings")
        if panel_scene_settings:
            layout.prop(ie3, "map_file_name", text="File Name")
            layout.prop(ie3, "resolution")
            layout.prop(ie3, "basic_map_count", text="Map Count")

            grid = layout.grid_flow(row_major=True, columns=4)
            grid.label(text="")
            grid.label(text="Name")
            grid.label(text="Keywords")
            grid.label(text="Color Depth")

            current_map_data_list = ie3.get_current_map_data_list()
            for map_data in current_map_data_list:
                t = map_data.get_type()
                if t == properties.MapType.Basic:
                    grid.label(text=map_data.default_name)
                    grid.prop(map_data, "display_name", text="")
                    grid.prop(map_data, "file_name_keywords", text="")
                    grid.prop(map_data, "color_depth", text="")
                elif t == properties.MapType.Special:
                    grid.label(text=map_data.default_name)
                    grid.label(text="")
                    grid.prop(map_data, "file_name_keywords", text="")
                    grid.label(text="")

            layout.operator(operators.OT_SaveSceneSettingGroup.bl_idname, text="Save")
            layout.operator(operators.OT_LoadSceneSettingGroup.bl_idname, text="Load")

        header_layer_creation, panel_layer_creation = layout.panel("layer_creation", default_closed=True)
        header_layer_creation.label(text="Layer Creation")
        if panel_layer_creation:
            self.layout.operator(operators.OT_CreateImageObj.bl_idname, text="Create image")
            self.layout.operator(operators.OT_CreateBasicLayerObj.bl_idname, text="Create basic layer")
            self.layout.operator(operators.OT_DuplicateLayerObj.bl_idname, text="Duplicate layer")

        header_active_layer, panel_active_layer = layout.panel("active_layer", default_closed=True)
        header_active_layer.label(text="Active Layer")
        if panel_active_layer:
            layer_obj_type = properties.get_layer_obj_type(context.active_object)
            if layer_obj_type == properties.LayerObjType.Image:
                grid = layout.grid_flow(row_major=True, columns=3)
                grid.label(text="")
                grid.label(text="File Path")
                grid.label(text="")

                current_map_data_list = ie3.get_current_map_data_list()
                for i, map_data in enumerate(current_map_data_list):
                    display_name = map_data.get_display_name()
                    grid.label(text=display_name)
                    grid.prop(map_data, "file_path", text="")
                    op = grid.operator(operators.OT_SelectImageObjMap.bl_idname, text="", icon="FILE_FOLDER")
                    op.map_data_index = i

                self.layout.operator(operators.OT_SelectImageObjMapsWithKeywords.bl_idname, text="Select maps with keywords")
                self.layout.prop(ie3, "b_use_grayscale_as_opacity")
                self.layout.prop(ie3, "opacity")

                self.layout.prop(ie3, "mapping_location")
                self.layout.prop(ie3, "mapping_rotation")
                self.layout.prop(ie3, "mapping_scale")

        header_snapping_and_alignment, panel_snapping_and_alignment = layout.panel("snapping_and_alignment", default_closed=True)
        header_snapping_and_alignment.label(text="Snapping & Alignment")
        if panel_snapping_and_alignment:
            self.layout.operator(operators.OT_SnapVertToClosestUvVert.bl_idname, text="Snap vert to closest uv vert")

            self.layout.label(text="Snap vert to uv edge")
            grid = layout.grid_flow(row_major=True, columns=3)
            grid.label(text="")
            op_y_p = grid.operator(operators.OT_SnapVertToUvEdge.bl_idname, text="↑")
            op_y_p.direction = operators.OT_SnapVertToUvEdge.Direction.YPlus.name
            grid.label(text="")
            op_x_m = grid.operator(operators.OT_SnapVertToUvEdge.bl_idname, text="←")
            op_x_m.direction = operators.OT_SnapVertToUvEdge.Direction.XMinus.name
            grid.operator(operators.OT_SnapVertToClosestUvEdge.bl_idname, text="Closest")
            op_x_p = grid.operator(operators.OT_SnapVertToUvEdge.bl_idname, text="→")
            op_x_p.direction = operators.OT_SnapVertToUvEdge.Direction.XPlus.name
            grid.label(text="")
            op_y_m = grid.operator(operators.OT_SnapVertToUvEdge.bl_idname, text="↓")
            op_y_m.direction = operators.OT_SnapVertToUvEdge.Direction.YMinus.name

            self.layout.operator(operators.OT_AlignVerts.bl_idname, text="Align verts")

        header_layer_movement, panel_layer_movement = layout.panel("layer_movement", default_closed=True)
        header_layer_movement.label(text="Layer Movement")
        if panel_layer_movement:
            row = layout.row()
            op_up = row.operator(operators.OT_MoveLayerObj.bl_idname, text="Up")
            op_up.target = operators.OT_MoveLayerObj.Target.Up.name
            op_down = row.operator(operators.OT_MoveLayerObj.bl_idname, text="Down")
            op_down.target = operators.OT_MoveLayerObj.Target.Down.name
            row = layout.row()
            op_top = row.operator(operators.OT_MoveLayerObj.bl_idname, text="Top")
            op_top.target = operators.OT_MoveLayerObj.Target.Top.name
            op_bottom = row.operator(operators.OT_MoveLayerObj.bl_idname, text="Bottom")
            op_bottom.target = operators.OT_MoveLayerObj.Target.Bottom.name

        header_viewport, panel_viewport = layout.panel("viewport", default_closed=True)
        header_viewport.label(text="Viewport")
        if panel_viewport:
            layout.prop(ie3, "display_map_name")
            self.layout.prop(ie3, "b_show_overlay")
            self.layout.prop(ie3, "overlay_opacity")

        header_export, panel_export = layout.panel("export", default_closed=True)
        header_export.label(text="Export")
        if panel_export:
            self.layout.operator(operators.OT_ExportMaps.bl_idname)

clss = [
    PT_Main,
]
