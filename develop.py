import os
import sys

repo_dir_path = os.path.dirname(__file__)
sys.path.append(repo_dir_path)

import importlib
import image_editor_3d.error as error
importlib.reload(error)
import image_editor_3d.dobj as dobj
importlib.reload(dobj)
import image_editor_3d.properties as properties
importlib.reload(properties)
import image_editor_3d.operators as operators
importlib.reload(operators)
import image_editor_3d.panels as panels
importlib.reload(panels)
import image_editor_3d
importlib.reload(image_editor_3d)


image_editor_3d.register()
