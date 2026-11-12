# Run: blender.exe -b -P bargello_anim.py -- <animDir> <outDir> [W H samples firstFrame lastFrame]
import bpy, sys, os, math, re, json
from mathutils import Vector

argv = sys.argv[sys.argv.index('--') + 1:]
ANIM, OUTD = argv[0], argv[1]
W = int(argv[2]) if len(argv) > 2 else 540
H = int(argv[3]) if len(argv) > 3 else 960
SAMPLES = int(argv[4]) if len(argv) > 4 else 32
F0 = int(argv[5]) if len(argv) > 5 else 0
F1 = int(argv[6]) if len(argv) > 6 else 10**6
BUMP = 0.85
HERE = os.path.dirname(os.path.abspath(__file__))
STITCH, WALLZ, WALL, FLOOR = 0.0085, 0.9, '#d8cdbf', '#7d5f46'
man = json.load(open(os.path.join(ANIM, 'manifest.json')))['frames']
os.makedirs(OUTD, exist_ok=True)

def srgb(hexstr):
    h = hexstr.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return (*[x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c], 1.0)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, 'SheenChair.glb'))
sc = bpy.context.scene
meshes = [o for o in sc.objects if o.type == 'MESH']
for o in meshes:
    if re.search('label', o.name, re.I): o.hide_render = True; o.hide_viewport = True
meshes = [o for o in meshes if not o.hide_render]
bpy.context.view_layer.update()
pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
ctr = (mn + mx) / 2
off = Vector((-ctr.x, -ctr.y, -mn.z))
for o in sc.objects:
    if o.parent is None: o.location += off
bpy.context.view_layer.update()

mat = bpy.data.materials.new('BargelloFabric'); mat.use_nodes = True
nt = mat.node_tree; nt.nodes.clear()
out = nt.nodes.new('ShaderNodeOutputMaterial'); bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
bsdf.inputs['Roughness'].default_value = 0.78
for name, val in (('Sheen Weight', 0.25), ('Sheen Roughness', 0.6)):
    if name in bsdf.inputs: bsdf.inputs[name].default_value = val
geo = nt.nodes.new('ShaderNodeNewGeometry'); mapn = nt.nodes.new('ShaderNodeMapping')
nt.links.new(geo.outputs['Position'], mapn.inputs['Vector'])
def img_node(noncolor):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(os.path.join(ANIM, man[0]['height' if noncolor else 'color']))
    n.image.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    n.projection = 'BOX'; n.projection_blend = 0.15; n.extension = 'REPEAT'; n.interpolation = 'Cubic'
    nt.links.new(mapn.outputs['Vector'], n.inputs['Vector']); return n
col = img_node(False); hgt = img_node(True)
bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 1.0
bump.inputs['Distance'].default_value = STITCH * BUMP
nt.links.new(hgt.outputs['Color'], bump.inputs['Height'])
nt.links.new(col.outputs['Color'], bsdf.inputs['Base Color'])
nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
for o in meshes:
    for slot in o.material_slots:
        if re.search('fabric', (slot.material.name if slot.material else '') + ' ' + o.name, re.I): slot.material = mat

def plain(name, hexc, rough):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value = srgb(hexc); b.inputs['Roughness'].default_value = rough
    return m
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0)); bpy.context.object.data.materials.append(plain('floor', FLOOR, 0.85))
bpy.ops.mesh.primitive_plane_add(size=30, location=(0, WALLZ, 6), rotation=(math.pi / 2, 0, 0)); bpy.context.object.data.materials.append(plain('wall', WALL, 0.95))
bpy.ops.mesh.primitive_plane_add(size=30, location=(-WALLZ * 1.5, 0, 6), rotation=(math.pi / 2, 0, math.pi / 2)); bpy.context.object.data.materials.append(plain('wall2', WALL, 0.95))
bpy.ops.object.light_add(type='SUN', location=(2.25, -2.7, 3.6))
sun = bpy.context.object; sun.data.energy = 3.2; sun.data.color = (1.0, 0.95, 0.87); sun.data.angle = math.radians(4)
sun.rotation_euler = (Vector((0, 0, 0.4)) - sun.location).to_track_quat('-Z', 'Y').to_euler()
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = srgb(WALL); bg.inputs['Strength'].default_value = 0.7

bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.sensor_fit = 'VERTICAL'; cam.data.angle_y = math.radians(30)
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 6.3
bpy.ops.object.empty_add(location=(0, 0, 0)); target = bpy.context.object
tc = cam.constraints.new('TRACK_TO'); tc.target = target; tc.track_axis = 'TRACK_NEGATIVE_Z'; tc.up_axis = 'UP_Y'
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = SAMPLES; sc.cycles.use_denoising = True
sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
try: sc.view_settings.view_transform = 'Filmic'
except Exception: pass
sc.render.image_settings.file_format = 'PNG'

def b3(v): return Vector((v[0], -v[2], v[1]))      # three.js (x,y,z) -> Blender (x,-z,y)
cur = None
for f in man:
    if f['i'] < F0 or f['i'] > F1: continue
    outp = os.path.join(OUTD, 'f%04d.png' % f['i'])
    if os.path.exists(outp): continue
    if cur != f['color']:
        col.image.filepath = os.path.join(ANIM, f['color']); col.image.reload()
        hgt.image.filepath = os.path.join(ANIM, f['height']); hgt.image.reload(); cur = f['color']
    mapn.inputs['Scale'].default_value = (1 / (f['texCols'] * STITCH),) * 3
    cam.location = b3(f['pos']); target.location = b3(f['tg'])
    cam.data.dof.focus_distance = f['dist']
    bpy.context.view_layer.update()
    sc.render.filepath = outp
    bpy.ops.render.render(write_still=True)
    print('WROTE', outp, flush=True)
print('ALLDONE')
