import bpy

from . import operators, panels, properties


clss = properties.clss + operators.clss + panels.clss

def register():
    global clss
    for cls in clss:
        bpy.utils.register_class(cls)
    bpy.types.Scene.ie3 = bpy.props.PointerProperty(type=properties.SceneData, name="Image Editor 3D")
    print("The addon \"Image Editor 3D\" registered.")

def unregister():
    del bpy.types.Scene.ie3
    global clss
    for cls in clss:
        bpy.utils.unregister_class(cls)
    print("The addon \"Image Editor 3D\" unregistered.")
