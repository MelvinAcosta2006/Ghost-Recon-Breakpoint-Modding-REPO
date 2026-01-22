bl_info = {
    "name": "GRB LODSelector & Mesh Tools",
    "author": "Acosta556 & ChatGPT",
    "version": (1, 1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Sidebar > GRB Tools",
    "description": "Generates LODSelectors, LOD .mesh files, vertex color setups, and bone pose tools for Ghost Recon Breakpoint modding.",
    "category": "Object",
}

import bpy
import os
import struct
import random
import re
from mathutils import Quaternion
from bpy.props import StringProperty, BoolProperty, EnumProperty, PointerProperty


# ------------------------------------------------------------------------
# Utility Functions
# ------------------------------------------------------------------------

def generate_13_digit_id():
    return random.randint(10**12, 10**13 - 1)

def pad_or_generate_base_id(override):
    clean_override = ''.join(filter(str.isdigit, override.strip()))
    if not clean_override:
        raise ValueError("Override must contain at least one digit.")
    if len(clean_override) > 13:
        raise ValueError("Base override must be 13 digits or fewer.")
    padding = 13 - len(clean_override)
    return clean_override + ''.join(str(random.randint(0, 9)) for _ in range(padding))

def get_template_paths():
    addon_dir = os.path.dirname(__file__)
    bin_dir = os.path.join(addon_dir, "bin")
    lodselector_path = os.path.join(bin_dir, "baked_entity_entries_Set1.entitymetadata")
    mesh_template_path = os.path.join(bin_dir, "baked_entity_entries_Set2.entitymetadata")
    return lodselector_path, mesh_template_path

def write_lodselector_binary(template_path, output_path, selector_id, lod_ids):
    selector_offset = 0x01
    lod_offsets = [0x1E, 0x42, 0x66, 0x8A, 0xAE]

    with open(template_path, "rb") as f:
        data = bytearray(f.read())

    data[selector_offset:selector_offset + 8] = struct.pack("<Q", selector_id)
    for i, offset in enumerate(lod_offsets):
        data[offset:offset + 8] = struct.pack("<Q", lod_ids[i])

    with open(output_path, "wb") as f:
        f.write(data)

def save_generated_ids_to_txt(output_path, selector_id, lod_ids):
    txt_path = os.path.splitext(output_path)[0] + ".txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("LOD Selector ID Dump\n")
        f.write("=====================\n")
        f.write(f"SelectorID: {selector_id}\n\n")
        for i, lid in enumerate(lod_ids):
            f.write(f"LOD{i}: {lid}\n")
    return txt_path

def generate_lod_mesh_variants(output_dir, base_name, lod_ids):
    _, mesh_template_path = get_template_paths()
    for i, lid in enumerate(lod_ids):
        with open(mesh_template_path, "rb") as f:
            data = bytearray(f.read())
        data[1:9] = struct.pack("<Q", lid)
        filename = f"10_-_{base_name}_LOD{i}.Mesh"
        lod_path = os.path.join(output_dir, filename)
        with open(lod_path, "wb") as f:
            f.write(data)


# ------------------------------------------------------------------------
# Property Groups
# ------------------------------------------------------------------------

class LODSelectorProps(bpy.types.PropertyGroup):
    output_dir: StringProperty(name="Output Directory", subtype='DIR_PATH')
    custom_template_path: StringProperty(name="Custom LODSelector Template", subtype='FILE_PATH', default="")
    use_selected_object_name: BoolProperty(
        name="Set Selected Object as LOD Name",
        description="Override export name using the active object's name",
        default=False
    )
    name_input: StringProperty(name="Name", default="")
    type_tag: StringProperty(name="Tags/Type", default="")
    base_id_override: StringProperty(name="Base ID Override", default="", maxlen=13)
    apply_decimate: BoolProperty(name="Apply Decimate", default=False)
    decimate_to_lod4: BoolProperty(
        name="Decimate to LOD4",
        default=False
    )
    decimate_ratio_start: bpy.props.FloatProperty(
        name="Starting Ratio (LOD1)",
        description="Decimate ratio for LOD1; subsequent LODs are halved",
        default=0.5,
        min=0.01,
        max=1.0,
        precision=3
    )

    gen_selector_id: StringProperty(name="Gen Selector ID", default="")
    gen_lod0: StringProperty(name="Gen LOD0", default="")
    gen_lod1: StringProperty(name="Gen LOD1", default="")
    gen_lod2: StringProperty(name="Gen LOD2", default="")
    gen_lod3: StringProperty(name="Gen LOD3", default="")
    gen_lod4: StringProperty(name="Gen LOD4", default="")

class GRBSettings(bpy.types.PropertyGroup):
    color_mode: EnumProperty(
        name="Color Mode",
        items=[('CAMO', "Camo‑able (default)", ""), ('NONCAMO', "Non‑Camo‑able", "")],
        default='CAMO'
    )
    cleanup_extra: BoolProperty(name="Clean Extra Vertex Colors", default=False)


# ------------------------------------------------------------------------
# Operators – LOD
# ------------------------------------------------------------------------

class LOD_OT_GenerateID(bpy.types.Operator):
    bl_idname = "lod.generate_id"
    bl_label = "Generate 13-Digit ID"

    def execute(self, context):
        props = context.scene.lodselector_props
        try:
            selector_id = pad_or_generate_base_id(props.base_id_override) if props.base_id_override else generate_13_digit_id()
            lod_ids = [str(int(selector_id) + i) for i in range(1, 6)]

            props.gen_selector_id = str(selector_id)
            props.gen_lod0 = lod_ids[0]
            props.gen_lod1 = lod_ids[1]
            props.gen_lod2 = lod_ids[2]
            props.gen_lod3 = lod_ids[3]
            props.gen_lod4 = lod_ids[4]

            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

class LOD_OT_WriteBinarySelector(bpy.types.Operator):
    bl_idname = "lod.write_binary_selector"
    bl_label = "Save LODSelector + LOD Meshes"

    def execute(self, context):
        props = context.scene.lodselector_props
        try:
            # Determine base name
            if props.use_selected_object_name:
                obj = context.view_layer.objects.active
                if not obj:
                    self.report({'ERROR'}, "No active object selected for name override.")
                    return {'CANCELLED'}
                base_name = bpy.path.clean_name(obj.name)
            else:
                base_name = f"{props.type_tag.strip()}_{props.name_input.strip()}" if props.type_tag.strip() else props.name_input.strip()
            if not base_name:
                self.report({'ERROR'}, "Name is required.")
                return {'CANCELLED'}

            selector_id = int(props.gen_selector_id)
            lod_ids = [int(props.gen_lod0), int(props.gen_lod1), int(props.gen_lod2), int(props.gen_lod3), int(props.gen_lod4)]

            prefix = "" if props.use_selected_object_name else "TP_"

            out_folder = os.path.join(
                props.output_dir,
                f"99999_-_{prefix}{base_name}.data"
            )
            os.makedirs(out_folder, exist_ok=True)

            template = props.custom_template_path or get_template_paths()[0]
            lod_file = os.path.join(
                out_folder,
                f"0_-_{prefix}{base_name}.LODSelector"
            )

            write_lodselector_binary(template, lod_file, selector_id, lod_ids)
            save_generated_ids_to_txt(lod_file, selector_id, lod_ids)
            generate_lod_mesh_variants(out_folder, base_name, lod_ids)

            self.report({'INFO'}, "Generated all files.")
            return {'FINISHED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

# ------------------------------------------------------------------------
# Operators – Batch LOD Export
# ------------------------------------------------------------------------

class LOD_OT_GenerateAndExportBatch(bpy.types.Operator):
    bl_idname = "lod.generate_export_batch"
    bl_label = "Generate and Export LOD Setup"
    bl_description = "Automatically generate IDs and export LODSelectors + meshes for all selected objects"

    def execute(self, context):
        props = context.scene.lodselector_props
        selected = [o for o in context.selected_objects if o.type == 'MESH']

        if not selected:
            self.report({'ERROR'}, "No mesh objects selected.")
            return {'CANCELLED'}

        if not props.output_dir:
            self.report({'ERROR'}, "Output directory is required.")
            return {'CANCELLED'}

        template = props.custom_template_path or get_template_paths()[0]
        exported = 0

        for obj in selected:
            # -------- Name resolution --------
            if props.use_selected_object_name:
                base_name = bpy.path.clean_name(obj.name)
            else:
                base_name = f"{props.type_tag.strip()}_{props.name_input.strip()}" \
                    if props.type_tag.strip() else props.name_input.strip()

            if not base_name:
                continue

            # -------- ID generation (respect override) --------
            try:
                if props.base_id_override:
                    selector_id = int(pad_or_generate_base_id(props.base_id_override))
                else:
                    selector_id = generate_13_digit_id()
            except Exception as e:
                self.report({'ERROR'}, f"Invalid Base ID Override: {e}")
                return {'CANCELLED'}

            lod_ids = [selector_id + i for i in range(1, 6)]

            # -------- Output paths --------
            out_folder = os.path.join(
                props.output_dir,
                f"99999_-_{base_name}.data"
            )
            os.makedirs(out_folder, exist_ok=True)

            lodselector_path = os.path.join(
                out_folder,
                f"0_-_{base_name}.LODSelector"
            )

            # -------- Write files --------
            write_lodselector_binary(template, lodselector_path, selector_id, lod_ids)
            save_generated_ids_to_txt(lodselector_path, selector_id, lod_ids)
            generate_lod_mesh_variants(out_folder, base_name, lod_ids)

            exported += 1

        self.report({'INFO'}, f"Generated and exported {exported} LOD setup(s).")
        return {'FINISHED'}

# ------------------------------------------------------------------------
# Operators – Mesh Tools
# ------------------------------------------------------------------------

class LOD_OT_MakeLOD0(bpy.types.Operator):
    bl_idname = "lod.make_lod0"
    bl_label = "Make LOD0"

    def execute(self, context):
        for obj in context.selected_objects:
            if not obj.name.endswith("_LOD0"):
                obj.name += "_LOD0"
        return {'FINISHED'}

class LOD_OT_DecimateDuplicate(bpy.types.Operator):
    bl_idname = "lod.decimate_duplicate"
    bl_label = "Duplicate & Decimate"

    DEFAULT_RATIO = 0.5

    def execute(self, context):
        props = context.scene.lodselector_props

        for obj in context.selected_objects:
            if obj.type != 'MESH':
                continue

            match = re.match(r"(.*)_LOD(\d+)$", obj.name)
            if not match:
                continue

            base, start_level = match.groups()
            start_level = int(start_level)
            if start_level >= 4:
                continue

            # Starting ratio for LOD1
            start_ratio = props.decimate_ratio_start if props.decimate_to_lod4 else \
                          (next((m.ratio for m in obj.modifiers if m.type == 'DECIMATE'), self.DEFAULT_RATIO))

            # Determine how many LODs to create
            max_level = 4 if props.decimate_to_lod4 else start_level + 1
            previous_obj = obj

            for lvl in range(start_level + 1, max_level + 1):
                new_obj = previous_obj.copy()
                new_obj.data = previous_obj.data.copy()
                new_obj.name = f"{base}_LOD{lvl}"
                context.collection.objects.link(new_obj)

                # Remove any existing decimate modifiers
                for m in [m for m in new_obj.modifiers if m.type == 'DECIMATE']:
                    new_obj.modifiers.remove(m)

                # Compute ratio
                steps = lvl - (start_level + 1)  # LOD1 = step 0
                ratio = max(start_ratio * (0.5 ** steps), 0.01)

                dec = new_obj.modifiers.new("Decimate", 'DECIMATE')
                dec.ratio = ratio

                if props.apply_decimate:
                    context.view_layer.objects.active = new_obj
                    bpy.ops.object.modifier_apply(modifier=dec.name)

                previous_obj = new_obj

        return {'FINISHED'}

class LOD_OT_ParentCleanArmature(bpy.types.Operator):
    bl_idname = "lod.parent_clean_armature"
    bl_label = "Parent & Clean Armature Modifiers"

    def execute(self, context):
        active = context.view_layer.objects.active
        if not active or not active.parent or active.parent.type != 'ARMATURE':
            self.report({'ERROR'}, "Active object must have an Armature parent.")
            return {'CANCELLED'}

        for obj in context.selected_objects:
            if obj != active and obj.type == 'MESH':
                for mod in [m for m in obj.modifiers if m.type == 'ARMATURE']:
                    obj.modifiers.remove(mod)
                mod = obj.modifiers.new("Armature", 'ARMATURE')
                mod.object = active.parent
                obj.parent = active.parent
        return {'FINISHED'}

class LOD_OT_ExportSelectedAsLOD0(bpy.types.Operator):
    bl_idname = "lod.export_selected_lod0"
    bl_label = "Export Selected Objects as LOD0"

    def execute(self, context):
        props = context.scene.lodselector_props
        base_id_str = props.gen_selector_id.strip()
        if not base_id_str.isdigit():
            self.report({'ERROR'}, "Valid base ID required (use Generate ID first).")
            return {'CANCELLED'}

        base_id = int(base_id_str)
        export_dir = props.output_dir or bpy.path.abspath("//")
        export_dir = os.path.join(export_dir, "LOD0_Exports")
        os.makedirs(export_dir, exist_ok=True)

        _, mesh_template_path = get_template_paths()
        exported = 0

        for i, obj in enumerate(context.selected_objects):
            if obj.type != 'MESH':
                continue

            current_id = base_id + i + 100  # Offset by 100 to avoid clashing with normal LOD IDs
            safe_name = bpy.path.clean_name(obj.name)
            name_tag = props.type_tag.strip() or "TP"
            filename = f"0_-_{name_tag}_{safe_name}_LOD0.Mesh"
            export_path = os.path.join(export_dir, filename)

            with open(mesh_template_path, "rb") as f:
                data = bytearray(f.read())
            data[1:9] = struct.pack("<Q", current_id)

            with open(export_path, "wb") as f:
                f.write(data)
            exported += 1

        self.report({'INFO'}, f"Exported {exported} mesh file(s) to {export_dir}")
        return {'FINISHED'}

# ------------------------------------------------------------------------
# Operators – Vertex Colors
# ------------------------------------------------------------------------

def ensure_vertex_color(mesh, name, domain, dtype, color):
    if name not in mesh.color_attributes:
        mesh.color_attributes.new(name=name, type=dtype, domain=domain)
    layer = mesh.color_attributes[name]
    for elem in layer.data:
        elem.color = color

class GRB_OT_PrepareMesh(bpy.types.Operator):
    bl_idname = "grb.prepare_mesh"
    bl_label = "Apply Vertex Colors"

    def execute(self, context):
        s = context.scene.grb_settings
        color1 = (1, 1, 1, 1) if s.color_mode == 'NONCAMO' else (0, 0, 0, 1)
        for obj in context.selected_objects:
            if obj.type == 'MESH':
                m = obj.data
                ensure_vertex_color(m, "Color", 'CORNER', 'BYTE_COLOR', (0, 0, 0, 1))
                ensure_vertex_color(m, "_COLOR_1", 'POINT', 'BYTE_COLOR', color1)
                ensure_vertex_color(m, "_COLOR_2", 'POINT', 'BYTE_COLOR', (0, 0, 0, 1))
                if s.cleanup_extra:
                    for layer in list(m.color_attributes):
                        if layer.name not in {"Color", "_COLOR_1", "_COLOR_2"}:
                            m.color_attributes.remove(layer)
        return {'FINISHED'}


# ------------------------------------------------------------------------
# Operators – Bone XML Tools
# ------------------------------------------------------------------------

def parse_tag(text, tag):
    m = re.search(f"<{tag}>(.*?)</{tag}>", text)
    return float(m.group(1)) if m else 0.0

class GRB_OT_CopyLoc(bpy.types.Operator):
    bl_idname = "grb.copy_loc"
    bl_label = "Copy Loc XML"
    def execute(self, context):
        b = context.active_pose_bone
        l = b.location
        bpy.context.window_manager.clipboard = f"<X>{l.x}</X>\n<Y>{l.y}</Y>\n<Z>{l.z}</Z>"
        return {'FINISHED'}

class GRB_OT_PasteLoc(bpy.types.Operator):
    bl_idname = "grb.paste_loc"
    bl_label = "Paste Loc XML"
    def execute(self, context):
        b = context.active_pose_bone
        c = context.window_manager.clipboard
        b.location = (parse_tag(c, "X"), parse_tag(c, "Y"), parse_tag(c, "Z"))
        return {'FINISHED'}

class GRB_OT_CopyRot(bpy.types.Operator):
    bl_idname = "grb.copy_rot"
    bl_label = "Copy Rot XML"
    def execute(self, context):
        q = context.active_pose_bone.rotation_quaternion
        bpy.context.window_manager.clipboard = f"<X>{q.x}</X>\n<Y>{q.y}</Y>\n<Z>{q.z}</Z>\n<W>{q.w}</W>"
        return {'FINISHED'}

class GRB_OT_PasteRot(bpy.types.Operator):
    bl_idname = "grb.paste_rot"
    bl_label = "Paste Rot XML"
    def execute(self, context):
        b = context.active_pose_bone
        c = context.window_manager.clipboard
        b.rotation_mode = 'QUATERNION'
        b.rotation_quaternion = Quaternion((parse_tag(c, "W"), parse_tag(c, "X"), parse_tag(c, "Y"), parse_tag(c, "Z")))
        return {'FINISHED'}


# ------------------------------------------------------------------------
# UI Panel
# ------------------------------------------------------------------------

class GRB_PT_ToolsPanel(bpy.types.Panel):
    bl_label = "GRB Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "GRB Tools"

    def draw(self, context):
        layout = self.layout
        p = context.scene.lodselector_props
        s = context.scene.grb_settings

        layout.label(text="📦 LOD Generator")
        layout.prop(p, "output_dir")
        layout.prop(p, "custom_template_path")
        layout.prop(p, "use_selected_object_name")
        if not p.use_selected_object_name:
            layout.prop(p, "name_input")
            layout.prop(p, "type_tag")
        layout.prop(p, "base_id_override")

        layout.separator()
        layout.label(text="One-Click Batch Export")
        layout.operator(
            "lod.generate_export_batch",
            icon='EXPORT'
        )

        layout.separator()
        layout.label(text="🧩 Mesh Tools")
        layout.prop(p, "apply_decimate")
        layout.operator("lod.make_lod0")
        layout.operator("lod.decimate_duplicate")
        layout.prop(p, "decimate_to_lod4")
        if p.decimate_to_lod4:
            layout.prop(p, "decimate_ratio_start")
        layout.operator("lod.parent_clean_armature")
        layout.operator("lod.export_selected_lod0")  # New LOD0 export button

        layout.separator()
        layout.label(text="🎨 Vertex Colors")
        layout.prop(s, "color_mode")
        layout.prop(s, "cleanup_extra")
        layout.operator("grb.prepare_mesh")

        layout.separator()
        layout.label(text="🦴 Bone Pose (Pose Mode Only)")
        layout.operator("grb.copy_loc")
        layout.operator("grb.paste_loc")
        layout.operator("grb.copy_rot")
        layout.operator("grb.paste_rot")


# ------------------------------------------------------------------------
# Register
# ------------------------------------------------------------------------

classes = [
    LODSelectorProps,
    GRBSettings,
    LOD_OT_GenerateID,
    LOD_OT_WriteBinarySelector,
    LOD_OT_GenerateAndExportBatch,
    LOD_OT_MakeLOD0,
    LOD_OT_DecimateDuplicate,
    LOD_OT_ParentCleanArmature,
    LOD_OT_ExportSelectedAsLOD0,
    GRB_OT_PrepareMesh,
    GRB_OT_CopyLoc,
    GRB_OT_PasteLoc,
    GRB_OT_CopyRot,
    GRB_OT_PasteRot,
    GRB_PT_ToolsPanel
]

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lodselector_props = PointerProperty(type=LODSelectorProps)
    bpy.types.Scene.grb_settings = PointerProperty(type=GRBSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.lodselector_props
    del bpy.types.Scene.grb_settings

if __name__ == "__main__":
    register()
