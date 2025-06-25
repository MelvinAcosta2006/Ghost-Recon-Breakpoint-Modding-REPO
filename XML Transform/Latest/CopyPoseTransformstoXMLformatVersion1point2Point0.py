bl_info = {
    "name": "Bone XML Exporter",
    "author": "Melvin Acosta + ChatGPT",
    "version": (1, 2, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar > Bone Utils",
    "description": "Copy and Paste pose bone local location to and from XML format. v1.2 'Literal Transform Edition' (1:1 XYZ mapping)",
    "category": "Animation",
}

import bpy
import re

class CopyBoneTransformOperator(bpy.types.Operator):
    bl_idname = "pose.copy_bone_xml"
    bl_label = "Copy Pose Bone as XML"
    bl_description = "Copy pose bone location (Literal XYZ – v1.2)"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE' or context.mode != 'POSE':
            self.report({'WARNING'}, "Must be in Pose Mode with an armature")
            return {'CANCELLED'}

        bone = context.active_pose_bone
        if bone is None:
            self.report({'WARNING'}, "No pose bone selected")
            return {'CANCELLED'}

        loc = bone.location
        xml = (
            f"<X>{loc.x}</X>\n"
            f"\t\t\t\t<Y>{loc.y}</Y>\n"
            f"\t\t\t\t<Z>{loc.z}</Z>"
        )

        context.window_manager.clipboard = xml
        self.report({'INFO'}, "Copied bone location (v1.2 – Literal XYZ)")
        return {'FINISHED'}


class PasteBoneTransformOperator(bpy.types.Operator):
    bl_idname = "pose.paste_bone_xml"
    bl_label = "Paste XML to Pose Bone"
    bl_description = "Paste location to pose bone (Literal XYZ – v1.2)"

    def execute(self, context):
        obj = context.active_object
        if obj is None or obj.type != 'ARMATURE' or context.mode != 'POSE':
            self.report({'WARNING'}, "Must be in Pose Mode with an armature")
            return {'CANCELLED'}

        bone = context.active_pose_bone
        if bone is None:
            self.report({'WARNING'}, "No pose bone selected")
            return {'CANCELLED'}

        xml = context.window_manager.clipboard
        try:
            x = float(re.search(r"<X>(.*?)</X>", xml).group(1))
            y = float(re.search(r"<Y>(.*?)</Y>", xml).group(1))
            z = float(re.search(r"<Z>(.*?)</Z>", xml).group(1))
        except Exception as e:
            self.report({'ERROR'}, f"Invalid XML: {e}")
            return {'CANCELLED'}

        bone.location = (x, y, z)
        self.report({'INFO'}, "Pasted bone location (v1.2 – Literal XYZ)")
        return {'FINISHED'}


class BoneXMLPanel(bpy.types.Panel):
    bl_label = "Bone XML Tools"
    bl_idname = "VIEW3D_PT_bone_xml_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Utils"

    def draw(self, context):
        layout = self.layout
        layout.label(text="v1.2 – Literal Transform Edition", icon='INFO')
        layout.operator("pose.copy_bone_xml", icon='COPYDOWN')
        layout.operator("pose.paste_bone_xml", icon='PASTEDOWN')


def register():
    bpy.utils.register_class(CopyBoneTransformOperator)
    bpy.utils.register_class(PasteBoneTransformOperator)
    bpy.utils.register_class(BoneXMLPanel)

def unregister():
    bpy.utils.unregister_class(CopyBoneTransformOperator)
    bpy.utils.unregister_class(PasteBoneTransformOperator)
    bpy.utils.unregister_class(BoneXMLPanel)

if __name__ == "__main__":
    register()
