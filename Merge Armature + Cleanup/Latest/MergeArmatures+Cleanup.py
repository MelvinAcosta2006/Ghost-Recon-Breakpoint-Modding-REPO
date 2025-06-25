import bpy
import re

def get_base_name(name):
    # Strips ".001", ".002", etc. to find the base name
    return re.sub(r"\.\d{3}$", "", name)

def merge_armatures_and_remove_duplicates():
    # Get the active armature (merge target)
    target = bpy.context.active_object
    if not target or target.type != 'ARMATURE':
        print("Active object must be an armature.")
        return

    # Collect target bone names
    target_bone_names = {bone.name for bone in target.data.bones}
    target_base_names = {get_base_name(name) for name in target_bone_names}

    # Enter edit mode on target
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode='EDIT')
    target_edit_bones = target.data.edit_bones

    for obj in bpy.context.selected_objects:
        if obj == target or obj.type != 'ARMATURE':
            continue

        print(f"Merging from {obj.name} into {target.name}")
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        source_bones = obj.data.edit_bones
        bpy.ops.object.mode_set(mode='OBJECT')

        # Temporarily make source active to access pose mode data
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode='EDIT')

        for bone in source_bones:
            base = get_base_name(bone.name)
            if base in target_base_names:
                print(f"Skipping duplicate bone: {bone.name}")
                continue

            # Switch back to target for adding the bone
            bpy.context.view_layer.objects.active = target
            bpy.ops.object.mode_set(mode='EDIT')
            new_bone = target_edit_bones.new(name=bone.name)
            new_bone.head = bone.head.copy()
            new_bone.tail = bone.tail.copy()
            new_bone.roll = bone.roll

            # Preserve parent if it exists and was also copied
            if bone.parent:
                parent_base = get_base_name(bone.parent.name)
                if parent_base in target_base_names:
                    new_bone.parent = target_edit_bones.get(bone.parent.name)

            # Add to target name sets to prevent future duplicates
            target_bone_names.add(bone.name)
            target_base_names.add(base)

            print(f"Copied bone: {bone.name}")

        # Delete source armature after merge (optional, or disable if needed)
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.data.objects.remove(obj, do_unlink=True)

    # Restore active to target and mode
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.mode_set(mode='OBJECT')
    print("Armature merge complete.")

# Run it
merge_armatures_and_remove_duplicates()
