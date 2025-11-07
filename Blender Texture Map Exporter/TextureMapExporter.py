import bpy
import os
import subprocess
import struct
import time
from PIL import Image

from bpy.props import StringProperty, IntProperty, EnumProperty, PointerProperty
from bpy.types import Panel, Operator, PropertyGroup

class TextureMapSettings(PropertyGroup):
    image_path: StringProperty(name="Image Path", subtype='FILE_PATH')
    texconv_path: StringProperty(name="texconv.exe Path", subtype='FILE_PATH')
    template_path: StringProperty(name="Template .TextureMap", subtype='FILE_PATH')
    output_path: StringProperty(name="Output Folder", subtype='DIR_PATH')
    tex_id: StringProperty(name="Texture ID", default="9696969696969")
    tex_type: EnumProperty(
        name="Texture Type",
        items=[
            ('Diffuse', 'Diffuse', ''),
            ('Normal', 'Normal', ''),
            ('Mask1', 'Mask1', ''),
        ],
        default='Diffuse'
    )

def compute_layout_bytes_dynamic(width: int, height: int, mip_count: int, fourcc: bytes) -> bytes:
    block_size = 16
    if fourcc == b'DXT1':
        block_size = 8
    elif fourcc in (b'DXT5', b'BC7\x00'):
        block_size = 16
    else:
        print(f"Unknown FourCC {fourcc}, defaulting to 16")

    print(f"DEBUG: Width={width}, Height={height}, MipCount={mip_count}, FourCC={fourcc}, BlockSize={block_size}")

    def mip_size(w, h):
        bw = max(1, (w + 3) // 4)
        bh = max(1, (h + 3) // 4)
        return bw * bh * block_size

    top_mip = mip_size(width, height)
    total_size = sum(mip_size(max(1, width >> i), max(1, height >> i)) for i in range(mip_count))
    return struct.pack('<II', total_size + 4, total_size) 
    print(f"----------------------------:")
    print(f"Computed Top Mip = {top_mip:#X}, Total = {total_size:#X}")
    print(f"----------------------------:")

class ConvertToTextureMapOperator(Operator):
    bl_idname = "image.convert_to_texturemap"
    bl_label = "Convert to TextureMap"

    def execute(self, context):
        props = context.scene.texturemap_settings
        auto_fit = True

        tex_format = {
            'Diffuse': ('BC7_UNORM', 0x00, 1),
            'Normal':  ('BC7_UNORM', 0x01, 0),
            'Mask1':   ('BC7_UNORM', 0x07, 0),
        }

        dds_format, type_val, gamma_val = tex_format[props.tex_type]
        base_name = os.path.splitext(os.path.basename(props.image_path))[0]
        dds_path = os.path.splitext(props.image_path)[0] + ".dds"

        suffix_map = {
            'Diffuse': '_DiffuseMapPC.TextureMap',
            'Normal': '_NormalMapPC.TextureMap',
            'Mask1': '_Mask1MapPC.TextureMap'
        }
        texmap_path = os.path.join(props.output_path, base_name + suffix_map[props.tex_type])

        try:
            # Step 0: Check and fix non-square images
            with Image.open(props.image_path) as img:
                width, height = img.size
                if width != height:
                    self.report({'WARNING'}, f"Image is not square: {width}x{height}")
                    if auto_fit:
                        new_size = max(width, height)
                        new_size = 2 ** (new_size - 1).bit_length()
                        img = img.resize((new_size, new_size), resample=Image.LANCZOS)
                        fixed_path = props.image_path.replace(".tif", f"_square.tif")
                        img.save(fixed_path)
                        props.image_path = fixed_path
                        base_name = os.path.splitext(os.path.basename(fixed_path))[0]
                        dds_path = os.path.splitext(fixed_path)[0] + ".dds"
                        texmap_path = os.path.join(props.output_path, base_name + suffix_map[props.tex_type])
                        self.report({'INFO'}, f"Resized to square: {new_size}x{new_size}")
                        width = height = new_size

            if width < 128 or height < 128:
                raise Exception("Minimum supported resolution is 128x128")

            # Step 1: Convert to DDS
            subprocess.run([
                props.texconv_path,
                '-f', dds_format,
                '-srgbi', '-srgbo',
                '-y',
                '-o', os.path.dirname(props.image_path),
                props.image_path
            ], check=True)
            time.sleep(0.2)

            # Step 2: Read DDS metadata and payload
            with open(dds_path, 'rb') as dds_file:
                dds_file.seek(0x0C)
                height = struct.unpack('<I', dds_file.read(4))[0]
                width = struct.unpack('<I', dds_file.read(4))[0]

                dds_file.seek(0x1C)
                mip_count = struct.unpack('<I', dds_file.read(4))[0]
                mip_count = max(mip_count, 1)

                dds_file.seek(0x54)
                fourcc = dds_file.read(4)

                dds_file.seek(0)
                dds_data = dds_file.read()

            # Step 3: Load template
            with open(props.template_path, 'rb') as tpl_file:
                tpl_data = bytearray(tpl_file.read())

            # Step 4: Inject header data
            struct.pack_into('<Q', tpl_data, 0x01, int(props.tex_id))  # ID
            tpl_data[0x2A] = type_val
            tpl_data[0x22] = gamma_val
            tpl_data[0x65] = gamma_val

            for offset in [0x0E, 0x4D]:
                struct.pack_into('<H', tpl_data, offset, width)
            for offset in [0x12, 0x51]:
                struct.pack_into('<H', tpl_data, offset, height)

            struct.pack_into('<I', tpl_data, 0x26, mip_count)
            struct.pack_into('<I', tpl_data, 0x59, mip_count)

            # Step 5: Inject layout bytes
            layout_bytes = compute_layout_bytes_dynamic(width, height, mip_count, fourcc)
            if len(layout_bytes) != 8:
                raise ValueError("Layout bytes must be exactly 8 bytes.")
            tpl_data[0x75:0x7C] = layout_bytes

            print(f"Injecting layout @0x75: {layout_bytes.hex()}")
            print(f"----------------------------:")
            print(f"Writing layout bytes to 0x74: {layout_bytes.hex(' ')}")
            print(f"tpl_data[0x74:0x7C] now = {tpl_data[0x74:0x7C].hex(' ')}")


            # Step 6: Inject DDS image
            tpl_data[0x7D:] = dds_data[0x94:]

            # Step 7: Write output
            with open(texmap_path, 'wb') as out_file:
                out_file.write(tpl_data)

            self.report({'INFO'}, f"Saved: {texmap_path}")
            return {'FINISHED'}

        except subprocess.CalledProcessError as e:
            self.report({'ERROR'}, f"texconv failed: {e}")
            return {'CANCELLED'}
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}

class ConvertTextureMapPanel(Panel):
    bl_label = "TextureMap Converter"
    bl_idname = "IMAGE_PT_texturemap_converter"
    bl_space_type = 'IMAGE_EDITOR'
    bl_region_type = 'UI'
    bl_category = 'TextureMap'

    def draw(self, context):
        layout = self.layout
        props = context.scene.texturemap_settings

        layout.prop(props, "image_path")
        layout.prop(props, "texconv_path")
        layout.prop(props, "template_path")
        layout.prop(props, "output_path")
        layout.prop(props, "tex_id")
        layout.prop(props, "tex_type")
        layout.operator(ConvertToTextureMapOperator.bl_idname, icon='FILE_TICK')

def register():
    bpy.utils.register_class(TextureMapSettings)
    bpy.types.Scene.texturemap_settings = PointerProperty(type=TextureMapSettings)
    bpy.utils.register_class(ConvertToTextureMapOperator)
    bpy.utils.register_class(ConvertTextureMapPanel)

def unregister():
    bpy.utils.unregister_class(TextureMapSettings)
    del bpy.types.Scene.texturemap_settings
    bpy.utils.unregister_class(ConvertToTextureMapOperator)
    bpy.utils.unregister_class(ConvertTextureMapPanel)

if __name__ == "__main__":
    register()
