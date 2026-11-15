"""PIE-only: give a real NPC a temporary query collider and mark its exposed-flesh test target."""
import unreal,json,traceback
from pathlib import Path
out=Path(unreal.Paths.project_saved_dir())/'SpellVFX'/'pie-target.json';out.parent.mkdir(parents=True,exist_ok=True)
try:
 w=unreal.EditorLevelLibrary.get_game_world()
 if not w:raise RuntimeError('PIE is not running')
 actors=unreal.GameplayStatics.get_all_actors_of_class(w,unreal.Actor)
 npc=next(a for a in actors if a.get_actor_label()=='Crowd Preview - White 01')
 hero=unreal.GameplayStatics.get_player_pawn(w,0);combat=hero.get_component_by_class(unreal.ReflectionsSpellCombatComponent)
 if not combat:raise RuntimeError('Hero combat component missing')
 tags=list(npc.get_editor_property('tags'));tags.append(unreal.Name('Flesh'));npc.set_editor_property('tags',tags)
 body=next(x for x in npc.get_components_by_class(unreal.SkeletalMeshComponent) if x.get_name()=='Body')
 body.set_collision_enabled(unreal.CollisionEnabled.QUERY_ONLY);body.set_collision_object_type(unreal.CollisionChannel.ECC_WORLD_DYNAMIC)
 body.set_collision_response_to_all_channels(unreal.CollisionResponseType.ECR_BLOCK)
 npcpos=npc.get_actor_location();target=npcpos+unreal.Vector(0,0,100)
 hero.set_actor_location(npcpos+unreal.Vector(-650,0,90),False,True)
 origin=hero.get_actor_location()+unreal.Vector(0,0,70)
 rot=unreal.MathLibrary.find_look_at_rotation(origin,target)
 unreal.GameplayStatics.get_player_controller(w,0).set_control_rotation(rot)
 transform=unreal.Transform(location=origin,rotation=rot,scale=unreal.Vector(1,1,1))
 combat.release_spell(unreal.HeroSpell.FIRE,transform)
 out.write_text(json.dumps({'stage':'shot','target':npc.get_actor_label(),'start':[origin.x,origin.y,origin.z],'target_location':[target.x,target.y,target.z]}))
except Exception as exc:out.write_text(json.dumps({'stage':'failed','error':str(exc),'trace':traceback.format_exc()}));unreal.log_error(traceback.format_exc())




