bl_info = {
    "name": "Bone XML Exporter",
    "author": "Melvin Acosta + ChatGPT",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "3D View > Sidebar > Bone Utils",
    "description": "Copies selected pose bone's local location as formatted XML",
    "category": "Animation",
}

import bpy

class CopyBoneTransformOperator(bpy.types.Operator):
    bl_idname = "pose.copy_bone_xml"
    bl_label = "Copy Pose Bone as XML"
    bl_description = "Copy the selected pose bone's local location as formatted XML"
    bl_options = {'REGISTER', 'UNDO'}

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
            f"\t\t\t\t<Y>{loc.z}</Y>\n"
            f"\t\t\t\t<Z>{-loc.y}</Z>"
        )

        context.window_manager.clipboard = xml
        self.report({'INFO'}, "Copied pose bone location to clipboard")
        return {'FINISHED'}


class BoneXMLPanel(bpy.types.Panel):
    bl_label = "Bone XML Tools"
    bl_idname = "VIEW3D_PT_bone_xml_tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Bone Utils"

    def draw(self, context):
        layout = self.layout
        layout.operator("pose.copy_bone_xml", icon='COPYDOWN')


def register():
    bpy.utils.register_class(CopyBoneTransformOperator)
    bpy.utils.register_class(BoneXMLPanel)

def unregister():
    bpy.utils.unregister_class(CopyBoneTransformOperator)
    bpy.utils.unregister_class(BoneXMLPanel)

if __name__ == "__main__":
    register()
