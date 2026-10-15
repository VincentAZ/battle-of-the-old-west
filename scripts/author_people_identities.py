"""Static identity pass: 23 public silhouettes on the existing Survivor rig.
No animation is authored or exported. Existing specialized costumes stay intact.
Run with Blender --background --python this_file -- [card ids].
"""
import sys, math, json
from pathlib import Path
import bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import author_survivor_variants as a
ROOT=Path(__file__).resolve().parents[1]
NAMES={c['id']:''.join(w.title() for w in c['id'].split('_')) for c in json.loads((ROOT/'game/data/cards.json').read_text())['cards'] if c['type']=='person' and c['id'] not in {'gatling_gunner','prospector','bounty_hunter','blacksmith'}}
NAMES['punk']='Punk'
# Colours are deliberately drawn from the printed identities, with weathered
# surfaces and restrained values suitable for the physical daylight scene.
PALETTE={
 'wyatt_earp':((.13,.10,.045),(.40,.26,.055)), 'hellfire_preacher':((.24,.06,.16),(.5,.38,.3)),
 'pinkerton_agent':((.40,.14,.15),(.66,.57,.40)), 'regulator':((.045,.14,.25),(.05,.24,.32)),
 'widow_with_a_shotgun':((.17,.32,.30),(.52,.37,.13)), 'quanah_parker':((.11,.24,.33),(.40,.035,.22)),
 'claim_jumper':((.20,.025,.09),(.065,.11,.15)), 'augustus_powder_pike':((.28,.045,.025),(.56,.31,.11)),
 'con_man':((.05,.15,.11),(.24,.48,.37)), 'cornelius_ashby_railroad_baron':((.15,.055,.12),(.23,.13,.19)),
 'bartender':((.12,.19,.26),(.29,.08,.20)), 'doc_holliday':((.075,.105,.085),(.13,.12,.11)),
 'barn_burner':((.08,.10,.12),(.33,.065,.045)), 'ringleader':((.04,.08,.085),(.52,.48,.30)),
 'sarah_winnemucca':((.20,.16,.085),(.54,.48,.30)), 'rustler':((.12,.11,.13),(.46,.025,.12)),
 'annie_oakley':((.045,.27,.10),(.34,.22,.12)), 'duelist':((.055,.27,.23),(.45,.31,.055)),
 'charles_goodnight':((.24,.19,.12),(.045,.16,.10)), 'vigilante':((.035,.10,.09),(.31,.055,.15)),
 'civil_war_veteran':((.17,.11,.065),(.55,.44,.29)), 'poker_alice':((.13,.075,.20),(.36,.26,.15)),
 'punk':((.027,.032,.035),(.03,.35,.26))}

def skin_material(key,color,metal=0):return a.material('M_Identity_'+key,color,.67,metal,metal==0)
def cap(m,helmet=False):
 a.loft('Helmet' if helmet else 'Cap',[(1.67,0,.03,.105,.12,0),(1.73,0,.03,.112,.12,.004),(1.80,0,.038,.065,.08,0),(1.817,0,.04,.003,.003,0)],m,a.HEAD)
def goggles(frame,lens):
 for x in [-.043,.043]:
  a.cylinder('Goggle_Rim',(x,-.105,1.653),.034,.025,frame,a.HEAD,axis=(0,-1,0))
  a.cylinder('Goggle_Lens',(x,-.121,1.653),.026,.007,lens,a.HEAD,axis=(0,-1,0))
 a.tube('Goggle_Strap',[(-.083,-.07,1.66),(-.1,.05,1.67),(0,.135,1.68),(.1,.05,1.67),(.083,-.07,1.66)],.008,frame,a.HEAD)
def mask(m,beak=False):
 a.ellipsoid('Respirator_Mask',(0,-.111,1.575),(.071,.055,.06),m,a.HEAD)
 for x in [-.06,.06]:a.cylinder('Mask_Filter',(x,-.146,1.57),.026,.035,m,a.HEAD,axis=(0,-1,0))
 if beak:
  a.loft('Rescue_Beaked_Mask',[(1.53,0,-.19,.011,.015,0),(1.58,0,-.15,.042,.08,0),(1.62,0,-.11,.066,.045,0)],m,a.HEAD)
def mohawk(m,long=False):
 from character_crests import fitted_crest
 obj,report=fitted_crest(bpy.data.objects['Survivor_Face_27Shapes'],a.arm,m,'Fitted_Mohawk',long=long)
 a.parts.append(obj)
 a.specs[m.name]['crest']={key:value for key,value in report.items() if key!='roots'}
def hood(m,large=False):
 a.loft('Open_Hood',[(1.45,0,.04,.15,.14,.025),(1.57,0,.04,.14,.16,.02),(1.7,0,.04,.135,.155,.02),(1.79,0,.05,.1,.12,.02),(1.83,0,.05,.009,.015,0)],m,a.HEAD,start=-.7,end=math.pi+.7)
def coat(m,short=False):
 obj=a.loft('Open_Split_Coat',[(.85 if short else .69,0,.035,.22,.18,.02),(1.02,0,.03,.20,.16,.02),(1.19,0,.04,.18,.17,.015),(1.40,0,.06,.17,.14,.01)],m,start=-1.1,end=math.pi+1.1)
 a.coat_skin(obj)
 for side in ['Left','Right']:a.sleeve('Coat_Cuff_'+side,'mixamorig:'+side+'ForeArm',m,.058,.044,.10,.95)
def shoulder(m,side='Left',large=False):
 bone='mixamorig:'+side+'Arm';p=a.arm.data.bones[bone].head_local+Vector((.03 if side=='Left' else -.03,0,.028))
 a.ellipsoid('Shoulder_Plate_'+side,p,(.12 if large else .09,.14,.075),m,bone)
def tanks(m,n=2):
 for i in range(n):
  x=(i-(n-1)/2)*.13
  a.cylinder('Pressure_Tank',(x,.225,1.245),.059,.38,m)
  for z in [1.08,1.4]:a.cylinder('Tank_Collar',(x,.225,z),.063,.017,a.material('Tank_Strap',(.032,.035,.032),.65,.65))
  a.tube('Tank_Feed',[(x,.225,1.44),(x+.045,.20,1.5),(.16,.08,1.41)],.012,m)
def beard(m,long=False):
 for i in range(11):
  x=(i-5)*.013;z=1.53-(.11 if long else .02)*(1-abs(i-5)/7)
  a.ellipsoid('Beard_Braid',(x,-.09,z),(.018,.024,.15 if long else .065),m,a.HEAD)
def necklace(m):
 for i in range(9):
  x=(i-4)*.036;z=1.365-.07*(1-abs(i-4)/5)
  a.cylinder('Necklace_Trophy',(x,-.183,z),.012,.065,m)
def hair(m,long=False,sidecut=False):
 from character_hair import author_hair
 author_hair(m,long=long,sidecut=sidecut)
def chest_panel(m):
 a.loft('Torso_Armour',[(1.06,0,.026,.177,.159,.004),(1.22,0,.03,.194,.18,.006),(1.37,0,.045,.19,.15,.004)],m,start=math.pi,end=math.tau)
def goggles_face(m):goggles(m['steel'],m['lens'])

def fitted_identity_goggles(card,frame,lens):
 from character_fitted_accessories import fitted_goggles
 parts,report=fitted_goggles(bpy.data.objects['Survivor_Face_27Shapes'],a.arm,frame,(.5,.5),(.5,.5),NAMES[card],lens_material=lens)
 a.parts.extend(parts)
 a.specs[frame.name]['fitted_goggles']=report

def design(card,m):
 from character_face import author_face
 author_face(card)
 from character_neck import fit_neck_seam
 fit_neck_seam()
 a.remove_equipment(('Survivor_Canteen','Survivor_BeltPouch','Survivor_Pouch','Survivor_Left_Cargo','Survivor_Right_Cargo'))
 base,accent=PALETTE[card];cloth=skin_material(card+'_cloth',base);trim=skin_material(card+'_accent',accent)
 garment=a.replace_cloth('Survivor_FieldShirt',card+'_Garment',cloth)
 a.replace_cloth('Survivor_CargoTrousers',card+'_Trousers',m['charcoal'])
 if card in {'rustler','punk'}:
  from author_vigilante_jaw_seam_candidate import attach_neck_expressions
  from character_fitted_accessories import fit_collar_weights
  body=bpy.data.objects['Survivor_Body'];face=bpy.data.objects['Survivor_Face_27Shapes']
  neck=attach_neck_expressions(body,face)
  a.specs[cloth.name]['neck_expressions']={k:v for k,v in neck.items() if k!='bindings'}
  a.specs[cloth.name]['collar']=fit_collar_weights(garment,body)
 # Each branch adds recognisable equipment and a distinct head silhouette.
 if card=='wyatt_earp':
  cap(cloth);a.cylinder('Captain_Cap_Brim',(0,-.045,1.708),.135,.014,cloth,a.HEAD);beard(m['ochre'],True);chest_panel(trim);tanks(trim,1)
  a.cylinder('Chest_Emitter',(0,-.20,1.26),.058,.025,m['brass'],axis=(0,-1,0))
 elif card=='hellfire_preacher':
  coat(cloth);hood(cloth);beard(m['ivory'],True);necklace(m['ivory']);a.cylinder('Ritual_Belt_Buckle',(0,-.17,1.02),.049,.018,trim,a.HIPS,axis=(0,-1,0))
 elif card=='pinkerton_agent':
  hood(cloth);coat(cloth,True);mask(m['ivory']);goggles(m['ivory'],m['teal']);necklace(m['steel'])
 elif card=='regulator':
  cap(trim,True);chest_panel(trim);shoulder(trim,'Left',True);shoulder(trim,'Right',True);tanks(m['steel'],3);mask(m['rubber']);a.cylinder('Single_Amber_Faceplate',(0,-.139,1.66),.054,.034,m['brass'],a.HEAD,axis=(0,-1,0))
  for side in ['Left','Right']:a.sleeve('Heavy_Arm_'+side,'mixamorig:'+side+'ForeArm',trim,.079,.058,.05,.9)
 elif card=='widow_with_a_shotgun':
  hood(trim);coat(trim,True);chest_panel(cloth);shoulder(cloth);hair(m['ivory']);a.box('Survival_Pack',(0,.20,1.2),(.26,.17,.36),cloth,bevel=.035)
 elif card=='quanah_parker':
  hair(m['ivory'],True,True);chest_panel(trim);shoulder(cloth);a.tube('Neck_Scarf',[(-.1,-.08,1.45),(0,-.12,1.435),(.1,-.08,1.45)],.031,trim)
 elif card=='claim_jumper':
  hood(cloth);mask(m['steel']);goggles(m['rubber'],m['lens']);a.box('Loot_Satchel',(.19,.06,1.0),(.20,.14,.27),trim,a.HIPS,.03)
  for i in range(3):a.box('Salvaged_Plate',(0,.21+i*.025,1.23+i*.08),(.26,.04,.23),m['steel'],bevel=.009)
 elif card=='augustus_powder_pike':
  hood(trim);coat(cloth);beard(m['ochre'],True);a.ellipsoid('Eyepatch',(-.043,-.104,1.655),(.037,.019,.033),m['leather'],a.HEAD)
  for side in ['Left','Right']:shoulder(m['brass'],side)
 elif card=='con_man':
  hair(m['teal'],True);mask(trim);goggles(trim,m['lens']);a.loft('High_Collar',[(1.39,0,.04,.135,.125,0),(1.5,0,.04,.12,.11,0)],cloth)
 elif card=='cornelius_ashby_railroad_baron':
  chest_panel(trim);shoulder(trim,'Left',True);shoulder(trim,'Right',True);hair(m['charcoal']);tanks(m['steel'],2)
  for side in ['Left','Right']:a.sleeve('Heavy_Gauntlet_'+side,'mixamorig:'+side+'ForeArm',m['steel'],.082,.055,.1,.94)
 elif card=='bartender':
  hair(trim,True);a.loft('Waist_Sash',[(.98,0,.025,.19,.159,.025),(1.10,0,.025,.18,.15,.025)],trim,a.HIPS);necklace(m['brass']);a.box('Water_Flask',(.20,.08,1.05),(.09,.07,.17),m['teal'],a.HIPS,.025)
 elif card=='doc_holliday':
  # Sculpt the derived skin itself: one enlarged brow, cheek and cranial side.
  # Applying identical deltas to all face keys keeps its expression topology.
  face=bpy.data.objects['Survivor_Face_27Shapes']
  inv=face.matrix_world.inverted().to_3x3()
  for v in face.data.vertices:
   p=face.matrix_world@v.co
   def falloff(center,radius):
    return math.exp(-sum(((p[i]-center[i])/radius[i])**2 for i in range(3))*2)
   crown=falloff((.06,.025,1.715),(.09,.12,.105))
   brow=falloff((.043,-.080,1.674),(.062,.055,.028))
   cheek=falloff((.067,-.080,1.607),(.046,.053,.052))
   delta=inv@Vector((.026*crown+.013*cheek,-.020*brow-.007*cheek,.019*crown+.005*brow))
   v.co+=delta
   if face.data.shape_keys:
    for key in face.data.shape_keys.key_blocks:key.data[v.index].co+=delta
  # The left arm grows in place; its shirt follows the same continuous warp.
  bone=a.arm.data.bones['mixamorig:LeftArm'];start,end=bone.head_local,bone.tail_local
  axis=(end-start).normalized()
  for obj in [bpy.data.objects['Survivor_Body'],bpy.data.objects[card+'_Garment']]:
   inverse=obj.matrix_world.inverted().to_3x3()
   for v in obj.data.vertices:
    p=obj.matrix_world@v.co;t=(p-start).dot(axis)/(end-start).length
    if -.1<t<1.1:
     nearest=start+(end-start)*t;radial=p-nearest
     if radial.length<.085:
      amount=.35*math.exp(-((t-.35)/.48)**2)*max(0.,1-(radial.length/.11)**4)
      v.co+=inverse@(radial*amount)
  # Practical scavenged gear supports the silhouette without hiding the face.
  a.sheet('Mutant_Worn_Bandolier',[
   [(-.135,-.094,1.415),(-.090,-.104,1.425)],
   [(-.065,-.174,1.304),(-.025,-.181,1.320)],
   [(.050,-.169,1.178),(.088,-.163,1.194)],
   [(.140,-.102,1.058),(.177,-.083,1.077)]],m['leather'])
  a.box('Mutant_Filter_Pouch',(-.19,.055,1.00),(.09,.075,.13),m['leather'],a.HIPS,.016)
  a.cylinder('Mutant_Dosimeter',(.18,-.09,1.02),.035,.015,m['steel'],a.HIPS,axis=(0,-1,0))
  a.cylinder('Mutant_Dosimeter_Face',(.18,-.099,1.02),.027,.004,m['ivory'],a.HIPS,axis=(0,-1,0))
 elif card=='barn_burner':
  mask(m['steel']);goggles(m['rubber'],m['brass']);tanks(trim,2);chest_panel(m['leather']);shoulder(m['steel'])
 elif card=='ringleader':
  hood(cloth);coat(cloth,True);mask(trim);goggles(trim,m['charcoal'])
  for i in range(3):a.box('Mask_Mouth_Slit',((i-1)*.025,-.168,1.576),(.009,.006,.02),m['charcoal'],a.HEAD,.002)
 elif card=='sarah_winnemucca':
  hood(trim);coat(cloth,True);mask(m['ivory'],True);goggles(m['brass'],m['lens']);a.box('Medical_Backpack',(0,.23,1.20),(.29,.18,.38),trim,bevel=.04)
  for sz in [(.13,.008,.04),(.04,.008,.13)]:a.box('Medic_Cross',(0,.326,1.24),sz,m['ivory'],bevel=.001)
 elif card=='rustler':
  mohawk(trim);fitted_identity_goggles(card,m['steel'],m['lens'])
  from character_fitted_accessories import scarf
  wrap,report=scarf(face,body,a.arm,trim,(.5,.5),'Scout_Fitted_Scarf',garment=garment)
  a.parts.append(wrap);a.specs[trim.name]['scarf']={k:v for k,v in report.items() if k!='bindings'}
  a.box('Recon_Radio',(0,.19,1.27),(.19,.1,.21),m['leather'],bevel=.02);a.tube('Radio_Aerial',[(.065,.22,1.39),(.065,.22,1.70)],.004,m['steel'])
 elif card=='annie_oakley':
  hood(cloth);coat(cloth,True);goggles(m['rubber'],m['lens']);hair(m['ochre'],True);a.box('Long_Range_Ammo',(.18,.05,1.02),(.09,.075,.18),trim,a.HIPS,.01)
 elif card=='duelist':
  coat(cloth,True);hair(m['charcoal'],True);goggles(m['teal'],m['lens']);shoulder(trim);necklace(m['brass'])
 elif card=='charles_goodnight':
  hair(trim,True);a.loft('Waist_Harness',[(.96,0,.025,.197,.16,.015),(1.06,0,.025,.191,.16,.015)],m['leather'],a.HIPS);shoulder(m['steel']);a.box('Signal_Control',(.17,-.06,1.02),(.10,.06,.11),m['teal'],a.HIPS,.015)
 elif card=='vigilante':
  cap(m['rubber']);goggles(m['rubber'],m['charcoal']);coat(cloth);a.box('Rose_Chest_Patch',(0,-.173,1.23),(.11,.015,.15),trim,bevel=.006);beard(m['ivory'])
 elif card=='civil_war_veteran':
  hair(m['ochre']);mask(m['steel']);chest_panel(trim);a.sheet('Chest_Bandage',[[(-.15,-.181,1.34),(-.13,-.186,1.40)],[(.12,-.181,1.09),(.16,-.186,1.14)]],m['ivory']);tanks(m['steel'],1)
 elif card=='poker_alice':
  a.loft('Wide_Conical_Hat',[(1.715,0,.03,.23,.23,0),(1.77,0,.03,.15,.15,0),(1.865,0,.03,.01,.01,0)],cloth,a.HEAD);coat(cloth,True);beard(m['charcoal'],True);necklace(trim)
 elif card=='punk':
  mohawk(trim,True);fitted_identity_goggles(card,m['rubber'],m['ivory']);chest_panel(cloth)
  from character_punk_equipment import respirator,pauldron
  equipment,report=respirator(face,a.arm,m['rubber'],(.5,.5),(.5,.5))
  for part in equipment:
   if part.name.endswith(('Filter_Rims','Filter_Grilles')):
    part.data.materials.clear();part.data.materials.append(m['steel'])
  a.parts.extend(equipment);a.specs[m['rubber'].name]['respirator']=report
  armor,report=pauldron(body,[garment]+[p for p in a.parts if p.name=='Torso_Armour'],a.arm,m['steel'],(.5,.5),(.5,.5))
  for part in armor:
   if part.name.endswith('Edge_Binding'):
    part.data.materials.clear();part.data.materials.append(m['rubber'])
  a.parts.extend(armor);a.specs[m['steel'].name]['pauldron']=report
  # Preserve the reviewed pauldron fit before replacing its original fitting
  # surface with the authored guard and its seated mounting hardware.
  original_panel=next(p for p in a.parts if p.name=='Torso_Armour')
  a.parts.remove(original_panel);bpy.data.objects.remove(original_panel,do_unlink=True)
  from character_punk_chest_guard import chest_guard
  guard_parts,report=chest_guard(a.arm,cloth,m['rubber'],m['steel'])
  a.parts.extend(guard_parts);a.specs[cloth.name]['chest_guard']=report
 # author_hair renames the groom when used. Other identities retain their
 # explicit helmets, hoods or mohawks without the unused base haircut.
 a.remove_equipment(('Survivor_HairCards',))
 # Preserve material noise and seams; equipment follows existing 53 bones.
 if card in {'rustler','punk'}:
  from character_wrist_straps import fitted_wrist_straps
  strap_material=m['leather'] if card=='rustler' else m['rubber']
  wrist_parts,report=fitted_wrist_straps(body,a.arm,strap_material,m['brass'],(.5,.5),{'Left':(.5,.5),'Right':(.5,.5)},NAMES[card])
  a.parts.extend(wrist_parts)
  a.specs[strap_material.name]['wrist_straps']={'method':report['method'],'wrists':[{k:v for k,v in wrist.items() if k!='body_supports'} for wrist in report['wrists']]}
 else:
  for side in ['Left','Right']:
   b=a.arm.data.bones['mixamorig:'+side+'ForeArm'];a.cylinder('Cuff_Rivet_'+side,b.head_local.lerp(b.tail_local,.8)+Vector((0,-.045,0)),.006,.007,m['brass'],'mixamorig:'+side+'ForeArm',axis=(0,-1,0))

# Reuse the exporter with explicit design injection; no rig or animation edits.
def main():
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('cards',nargs='*',choices=sorted(NAMES))
 parser.add_argument('--output',type=Path,default=ROOT/'art/characters/identities')
 parser.add_argument('--render',action='store_true')
 args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
 a.NAMES=NAMES;a.OUT=args.output.resolve()
 for card in args.cards or NAMES:a.author(card,lambda m,card=card:design(card,m))

if __name__=='__main__':main()
