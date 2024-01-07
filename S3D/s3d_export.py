import bpy

from enum import Enum

# ---------------------------------------------------------------------

class ReliableTxtEncoding(Enum):
    UTF_8 = 'utf-8'
    UTF_16 = 'utf-16-be'
    UTF_16_REVERSED = 'utf-16-le'
    UTF_32 = 'utf-32'

# ---------------------------------------------------------------------

class ReliableTxtFileWriter:
    def open(filepath, reliabletxt_encoding):
        encoding = reliabletxt_encoding.value
        
        file = open(filepath, 'w', encoding=encoding, newline='\n')
        file.write('\ufeff')
        
        return file

# ---------------------------------------------------------------------

class WsvSerializer:
    def __needs_doublequotes(str):
        if str == '' or str == '-':
            return True
        for char in str:
            if char == '\n' or char == '"' or char == '#' or char.isspace():
                return True
        return False
    
    def serialize_value(str):
        if str is None:
            return '-'
        elif not WsvSerializer.__needs_doublequotes(str):
            return str
        
        result = '"'
        for char in str:
            if char == '\n':
                result += '"/"'
            elif char == '"':
                result += '""'
            else:
                result += char
        result += '"'
        return result

# ---------------------------------------------------------------------

class SmlFileWriter:
    def __init__(self, filepath, reliabletxt_encoding):
        self.file = ReliableTxtFileWriter.open(filepath, reliabletxt_encoding)
        self.level = 0
        
    def __write_name(self, name):
        indent = '\t' * self.level
        escaped_name = WsvSerializer.serialize_value(name)
        self.file.write(indent + name)
    
    def begin_element(self, name):
        self.__write_name(name)
        self.file.write('\n')
        self.level += 1
    
    def end_element(self):
        self.level -= 1
        self.__write_name('End')
        if self.level > 0:
            self.file.write('\n')
    
    def begin_attribute(self, name):
        self.__write_name(name)
        
    def end_attribute(self):
        self.file.write('\n')
    
    def write_attribute_number(self, number):
        self.file.write(' ' + str(number))
      
    def write_attribute_numbers(self, numbers):
        for number in numbers:
            self.write_attribute_number(number)
            
    def write_attribute_string(self, str):
        escaped_str = WsvSerializer.serialize_value(str)
        self.file.write(' ' + escaped_str)
        
    def numbers_attribute(self, name, numbers):
        self.begin_attribute(name)
        self.write_attribute_numbers(numbers)
        self.end_attribute()
        
    def number_attribute(self, name, number):
        self.begin_attribute(name)
        self.write_attribute_number(number)
        self.end_attribute()
    
    def string_numbers_attribute(self, name, str, numbers):
        self.begin_attribute(name)
        self.write_attribute_string(str)
        self.write_attribute_numbers(numbers)
        self.end_attribute()
    
    def string_attribute(self, name, str):
        self.begin_attribute(name)
        self.write_attribute_string(str)
        self.end_attribute()
    
    def strings_attribute(self, name, *strs):
        self.begin_attribute(name)
        for str in strs:
            escaped_str = WsvSerializer.serialize_value(str)
            self.file.write(' ' + escaped_str)
        self.end_attribute()
    
    def close(self):
        self.file.close()

# ---------------------------------------------------------------------

from datetime import datetime
import bmesh
from mathutils import Vector


class S3DFileWriter:
    def __init__(self, filepath, reliabletxt_encoding, triangulate):
        self.triangulate = triangulate
        self.written_meshes = []
        
        self.writer = SmlFileWriter(filepath, reliabletxt_encoding)
        self.write_root()
        self.writer.close()
    
    
    def write_root(self):
        self.writer.begin_element('S3D')
        
        self.writer.string_attribute('Version', '0.1')
        
        self.write_meta()
        #self.write_environment()
        self.write_materials()
        self.write_scene()
        
        self.writer.end_element()
    
    
    def write_meta(self):
        self.writer.begin_element('Meta')
        self.writer.string_attribute('FileName', bpy.data.filepath)
        now = datetime.now()
        export_date = now.strftime('%Y-%m-%d')
        export_time = now.strftime('%H:%M:%S')
        self.writer.strings_attribute('ExportDate', export_date, export_time)
        self.writer.end_element()
    
    
    #def write_environment(self):
    #    self.writer.begin_element('Environment')
    #    background_color = bpy.context.scene.world.color
    #    self.writer.numbers_attribute('Color', background_color)
    #    self.writer.end_element()
    
    
    def get_texture(self, material):
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'TEX_IMAGE':
                    return bpy.path.basename(node.image.filepath)
        return None
    
    
    def get_color(self, material):
        if material.use_nodes:
            for node in material.node_tree.nodes:
                if node.type == 'BSDF_DIFFUSE':
                    return node.inputs[0].default_value
        return None
    
    
    def write_material(self, material):
        self.writer.begin_element('ClassicMaterial')
        self.writer.string_attribute('Name', material.name)
        
        color = self.get_color(material)
        if color:
            self.writer.numbers_attribute('DiffuseColor', color)
        
        texture = self.get_texture(material)
        if texture:
            self.writer.begin_element('DiffuseMap')
            self.writer.string_attribute('FilePath', texture)
            self.writer.end_element()
            
        self.writer.end_element()
    
    
    def write_materials(self):
        #self.writer.begin_element('Materials')
        materials = bpy.data.materials
        for material in materials:
            self.write_material(material)
        #self.writer.end_element()
    
    
    def write_scene(self):
        #self.writer.begin_element('Scene')
        #self.writer.begin_element('Children')
        
        scene = bpy.context.scene
        root_objects = (obj for obj in scene.objects if not obj.parent)
        for obj in root_objects:
            self.write_node(obj)
        
        #self.writer.end_element()
        #self.writer.end_element()
    
    
    #def write_light_data(self, light_obj):
    #    lightdata = light_obj.data
    #    self.writer.numbers_attribute('Color', lightdata.color)
    
    
#    def write_camera_data(self, camera_obj):
#        cameradata = camera_obj.data
#        if cameradata.type == 'PERSP':
#            self.writer.string_attribute('Type', 'Perspective')
#            self.writer.number_attribute('HorizontalFOV', cameradata.angle_x)
#            self.writer.number_attribute('VerticalFOV', cameradata.angle_y)
#        
#        render = bpy.context.scene.render
#        aspect_ratio = render.resolution_x / render.resolution_y
#        self.writer.number_attribute('AspectRatio', aspect_ratio)
    
    
    def write_mesh_data(self, mesh_obj):
        meshdata = mesh_obj.data
        mesh_name = meshdata.name
        #if mesh_name in self.written_meshes:
        #    self.writer.string_attribute('MeshDataInstance', mesh_name)
        #    return
        
        self.written_meshes.append(mesh_name)
        #self.writer.begin_element('MeshData')
        
        num_materials = len(mesh_obj.material_slots)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_mesh_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = bpy.data.meshes.new_from_object(eval_mesh_obj)
        
        #self.writer.string_attribute('Name', mesh_name)
        
        cloned_mesh = bmesh.new()
        cloned_mesh.from_mesh(meshdata)
        
        cloned_eval_mesh = bmesh.new()
        cloned_eval_mesh.from_mesh(eval_mesh)
        if self.triangulate:
            bmesh.ops.triangulate(cloned_mesh, faces=cloned_mesh.faces[:])
            bmesh.ops.triangulate(cloned_eval_mesh, faces=cloned_eval_mesh.faces[:])
        
        #self.writer.begin_attribute('Vertices')
        for vertex in cloned_mesh.verts:
            self.writer.begin_attribute('v')
            self.writer.write_attribute_numbers(vertex.co)
            self.writer.end_attribute()
        
#        self.writer.begin_attribute('PolySizes')
#        for face in cloned_mesh.faces:
#            self.writer.write_attribute_number(len(face.verts))
#        self.writer.end_attribute()
#        
#        self.writer.begin_attribute('Polygons')
        for face in cloned_mesh.faces:
            self.writer.begin_attribute('f')
            for vert in face.verts:
                self.writer.write_attribute_number(vert.index)
            self.writer.end_attribute()
        
#        if num_materials > 1:
#            self.writer.begin_attribute('MaterialIndices')
#            for face in cloned_mesh.faces:
#                self.writer.write_attribute_number(face.material_index)
#            self.writer.end_attribute()
#        
#        self.writer.begin_attribute('Normals')
#        for face in cloned_eval_mesh.faces:
#            for vert in face.verts:
#                self.writer.write_attribute_numbers(vert.normal)
#        self.writer.end_attribute()
#        
#        normal_index = 0
#        self.writer.begin_attribute('NormalIndices')
#        for face in cloned_eval_mesh.faces:
#            for vert in face.verts:
#                self.writer.write_attribute_number(normal_index)
#                normal_index += 1
#        self.writer.end_attribute()
#        
#        uv_lay = cloned_eval_mesh.loops.layers.uv.active
#        print(uv_lay)
#        self.writer.begin_attribute('UVs')
#        for face in cloned_eval_mesh.faces:
#            for loop in face.loops:
#                uv = loop[uv_lay].uv
#                self.writer.write_attribute_numbers(uv)
#        self.writer.end_attribute()
#        
#        uv_index = 0
#        self.writer.begin_attribute('UVIndices')
#        for face in cloned_eval_mesh.faces:
#            for vert in face.verts:
#                self.writer.write_attribute_number(uv_index)
#                uv_index += 1
#        self.writer.end_attribute()
        
        #self.writer.end_element()
    
    
    def write_transform(self, obj):
        mat = obj.matrix_local
        self.writer.numbers_attribute('Matrix', [*mat.row[0], *mat.row[1], *mat.row[2], *mat.row[3]])
        
        self.writer.begin_element('Transform')
        
        if obj.location != Vector():
            self.writer.numbers_attribute('Translation', obj.location)
        
        if obj.rotation_mode == 'QUATERNION':
            self.writer.string_numbers_attribute('Rotation', 'Q', obj.rotation_quaternion)
        elif obj.rotation_mode == 'AXIS_ANGLE':
            self.writer.string_numbers_attribute('Rotation', 'AA', obj.rotation_axis_angle)
        else:
            if obj.rotation_euler.x != 0 or obj.rotation_euler.y != 0 or obj.rotation_euler.z != 0:
                self.writer.string_numbers_attribute('Rotation', str(obj.rotation_mode), obj.rotation_euler)
        
        if obj.scale != Vector((1,1,1)):
            self.writer.numbers_attribute('Scale', obj.scale)
        
        print(obj.rotation_mode)
        self.writer.end_element()
    
    
    def write_node(self, obj):
        obj_typename = Utils.get_object_typename(obj)
        #self.writer.begin_element(obj_typename)
        
        if obj_typename == 'Light' or obj_typename == 'Camera':
            return
        #    self.write_light_data(obj)
        #elif :
        #    self.write_camera_data(obj)
        
        self.writer.string_attribute('g', obj.name)
        
        #self.write_transform(obj)
        
        #if obj.material_slots:
        #    self.writer.begin_attribute('Materials')
        #    for material in obj.material_slots:
        #        self.writer.write_attribute_number(material.name)
        #    self.writer.end_attribute()
        
        if obj_typename == 'Mesh':
            self.write_mesh_data(obj)
        #elif obj_typename == 'Light':
        #    self.write_light_data(obj)
        #elif obj_typename == 'Camera':
        #    self.write_camera_data(obj)
        
        if obj.children:
            #self.writer.begin_element('Children')
            for child_obj in obj.children:
                self.write_node(child_obj)
            #self.writer.end_element()
            
        #self.writer.end_element()
    

# ---------------------------------------------------------------------

class Utils:
    def get_object_typename(obj):
        obj_type = obj.type
        obj_types = bpy.context.object.bl_rna.properties['type'].enum_items
        type = obj_types.get(obj_type)
        return type.name

# ---------------------------------------------------------------------


from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# ---------------------------------------------------------------------

class S3DExporter(Operator, ExportHelper):
    """S3D Exporter"""
    bl_idname = 'stenway.s3d_export'
    bl_label = 'Export S3D'

    filename_ext = '.s3d'

    filter_glob: StringProperty(
        default='*.s3d',
        options={'HIDDEN'},
        maxlen=255,
    )
    
#    encoding: EnumProperty(
#        name='Encoding',
#        description='Choose one ReliableTXT encoding',
#        items=(
#            (ReliableTxtEncoding.UTF_8.value, 'UTF-8', 'UTF-8 with BOM'),
#            (ReliableTxtEncoding.UTF_16.value, 'UTF-16', 'UTF-16 Big Endian with BOM'),
#            (ReliableTxtEncoding.UTF_16_REVERSED.value, 'UTF-16 Reversed', 'UTF-16 Little Endian with BOM'),
#            (ReliableTxtEncoding.UTF_32.value, 'UTF-32', 'UTF-32 Big Endian with BOM'),
#        ),
#        default=ReliableTxtEncoding.UTF_8.value,
#    )
    
    triangulate: BoolProperty(
        name='Triangulate',
        description='Convert polygons to triangles',
        default=False,
    )
    
    exportNormals: BoolProperty(
        name='Export Normals',
        description='Export normals',
        default=True,
    )
    
    exportTexcoords: BoolProperty(
        name='Export Texcoords',
        description='Export texture coordinates',
        default=True,
    )

    def execute(self, context):
        writer = S3DFileWriter(self.filepath, ReliableTxtEncoding("utf-8"), self.triangulate)
        return {'FINISHED'}


def menu_func_export(self, context):
    self.layout.operator(S3DExporter.bl_idname, text='Static 3D (.s3d)')


def register():
    bpy.utils.register_class(S3DExporter)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(S3DExporter)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == '__main__':
    register()
    
    bpy.ops.stenway.s3d_export('INVOKE_DEFAULT')
