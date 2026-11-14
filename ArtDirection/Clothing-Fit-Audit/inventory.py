import bpy, pathlib, json
root=pathlib.Path(r'C:\Users\zachc\Documents\Unreal Projects\reflections\ArtDirection\Three-Londons-Wardrobe')
files=[root/'Merchant/Merchant.blend',root/'Red London/FerryPilot/FerryPilot_Outfit.blend',root/'Red London/Bridge Guard/BridgeGuard-Outfit.blend',root/'Red London/Festival Drummer/FestivalDrummer-Outfit.blend',root/'Red London/Archive Apprentice/ArchiveApprentice.blend',root/'Red London/Glass Artisan/GlassArtisan.blend',root/'White London - Rags and Tattoos/IvenMetaHuman/IvenRook_MetaHuman_Outfit.blend',root/'Hero/Hero_Wardrobe.blend']
out={}
for path in files:
 try:
  bpy.ops.wm.open_mainfile(filepath=str(path))
  out[str(path)]=[{'name':o.name,'type':o.type,'v':len(o.data.vertices) if o.type=='MESH' else None,'modifiers':[(m.name,m.type,getattr(getattr(m,'object',None),'name',None)) for m in o.modifiers] if o.type=='MESH' else []} for o in bpy.data.objects if o.type in {'MESH','ARMATURE'}]
 except Exception as ex: out[str(path)]={'error':str(ex)}
with open(r'ArtDirection/Clothing-Fit-Audit/inventory.json','w') as f: json.dump(out,f,indent=2)
