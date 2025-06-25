import bpy

def delete_duplicate_bones():
    # Get the active armature (the one to keep bones from)
    target = bpy.context.active_object
    if not target or target.type != 'ARMATURE':
        print("Active object is not a valid armature.")
        return

    target_bone_names = {bone.name for bone in target.data.bones}

    # Iterate through selected armatures, excluding the active one
    for obj in bpy.context.selected_objects:
        if obj == target or obj.type != 'ARMATURE':
            continue

        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        edit_bones = obj.data.edit_bones
        for bone in list(edit_bones):
            if bone.name in target_bone_names:
                edit_bones.remove(bone)
                print(f"Removed duplicate bone: {bone.name} from {obj.name}")

        bpy.ops.object.mode_set(mode='OBJECT')

    # Restore active object
    bpy.context.view_layer.objects.active = target
    print("Duplicate bone cleanup complete.")

# Run it
delete_duplicate_bones()
