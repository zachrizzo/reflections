"""Ambient NPC animation library: the single source of truth for every clip.

Each clip is generated with UE 5.9 Kimodo (model nvidia/Kimodo-SOMA-RP-v1.1, commercial-use licence) on a
MetaHuman (BP_Kellan, /Game/MetaHumans/Common metahuman_base_skel), then baked to
/Game/Animation/KimodoTests/AmbientLibrary/<NN>_<Category>/AS_Amb_<Category>_<Clip>.

Clip fields
  id       short PascalCase name, unique inside its category
  prompts  [(frame offset inside the clip, sentence)]. One short sentence per beat: a single long sentence
           collapses into a held pose, so multi-step clips are keyed beat by beat.
  frames   length at 30 fps (default 240 = 8 s)
  still    True for a quiet held pose (standing guard, dozing): the review does not flag it as frozen
  kind     'loop'   a repeating activity: the NPC system chains takes / crossfades back to the start
           'action' a one-shot gesture or beat that starts and ends near a relaxed stand
  props    what the hand would hold. Kimodo is not prop-aware and SOMA has no fingers, so props attach to
           hand_r / hand_l sockets at runtime and the hands stay open.
  jobs     which NPC jobs or situations use it (trades match ArtDirection/NpcBehavior/Spike/gen_lives.py)

Everything is miming: there is no axe, anvil, bench or partner in the generation scene. Seated clips sit on an
invisible seat at Kimodo's default seat height, so the runtime must place them on a bench or stool.
"""

FPS = 30
DEFAULT_FRAMES = 240
SEED_BASE = 9000


def C(cid, *beats, frames=DEFAULT_FRAMES, kind='loop', props=(), jobs=(), rev=0, still=False):
    """beats: sentences (spread evenly) or (offset, sentence) pairs."""
    if beats and all(isinstance(b, str) for b in beats):
        step = frames // len(beats)
        beats = [(i * step, b) for i, b in enumerate(beats)]
    return {'id': cid, 'prompts': [(int(o), s) for o, s in beats], 'frames': frames, 'kind': kind,
            'props': list(props), 'jobs': list(jobs), 'rev': rev, 'still': still}


ANY = ('anyone',)

CATEGORIES = [
    ('Idle', 'Standing idles: what anyone does while waiting or between tasks', [
        C('Relaxed', 'A person stands relaxed with arms at the sides, breathing calmly and shifting weight slightly.', jobs=ANY, still=True),
        C('WeightShift', 'A person stands and shifts their weight onto the left leg, the hips swaying to the left.',
          'A person shifts their weight onto the right leg, the hips swaying to the right.',
          'A person shifts their weight back onto the left leg and glances to the side.', jobs=ANY, rev=1),
        C('LookAround', (0, 'A person stands still and looks slowly to the left.'),
          (90, 'A person stands still and looks slowly to the right.'),
          (170, 'A person stands relaxed and looks straight ahead.'), jobs=ANY, still=True),
        C('ArmsCrossed', 'A person stands with arms crossed over the chest, shifting weight and looking around.', jobs=ANY, still=True),
        C('HandsOnHips', 'A person stands with both hands on the hips, looking around.', jobs=ANY, still=True),
        C('HandsBehindBack', 'A person stands upright with hands clasped behind the back, rocking slightly on the heels.',
          jobs=('guard', 'merchant', 'noble'), still=True),
        C('Stretch', (0, 'A person stands and stretches both arms high above the head.'),
          (100, 'A person stands and twists the torso from side to side, stretching.'),
          (180, 'A person stands relaxed with arms at the sides.'), kind='action', jobs=ANY),
        C('Yawn', (0, 'A person stands and yawns, covering the mouth with one hand.'),
          (110, 'A person stands and rubs the eyes, tired.'),
          (170, 'A person stands relaxed, shifting weight.'), kind='action', jobs=ANY),
        C('ScratchHead', 'A person stands and scratches the back of the head, puzzled.',
          'A person stands with one hand on the chin, thinking.', kind='action', jobs=ANY),
        C('ShadeEyes', (0, 'A person stands and raises one hand to shade the eyes, looking far into the distance.'),
          (150, 'A person stands and lowers the hand, relaxed.'), kind='action', jobs=('guard', 'fisher', 'farmer')),
        C('Impatient', 'A person stands and taps the right foot on the ground again and again, impatient.',
          'A person puts both hands on the hips, sighs and looks to the left and the right.',
          'A person drops the hands to the sides and taps the right foot again and again.', jobs=ANY, rev=1),
        C('Cold', 'A person stands hunched against the cold, rubbing the upper arms with both hands and stamping the feet.',
          jobs=ANY),
    ]),
    ('Social', 'Talking, listening and reacting to someone standing in front', [
        C('TalkCasual', 'A person talks to someone in front of them, moving the right hand up and down while explaining.',
          'A person talks, opening both hands outward, palms up.',
          'A person talks, lowering the hands and nodding, then lifting the right hand again.', jobs=ANY, rev=1),
        C('TalkAnimated', 'A person stands telling an exciting story, gesturing widely with both arms.',
          'A person stands talking excitedly, pointing and waving the arms.', jobs=ANY),
        C('ListenNod', 'A person stands listening to someone in front of them, nodding, arms relaxed.', jobs=ANY, still=True),
        C('Laugh', (0, 'A person stands and laughs loudly, leaning back.'),
          (100, 'A person stands laughing and slaps the thigh.'),
          (180, 'A person stands smiling, relaxed.'), kind='action', jobs=ANY),
        C('Argue', (0, 'A person stands arguing angrily with someone in front of them, pointing a finger.'),
          (100, 'A person stands arguing, throwing both hands up in frustration.'),
          (180, 'A person stands angrily with arms crossed.'), jobs=ANY),
        C('WhisperGossip', (0, 'A person leans in and whispers to someone beside them, a hand raised to the mouth.'),
          (130, 'A person stands upright and glances around secretively.'), kind='action', jobs=ANY),
        C('WaveGreet', (0, 'A person stands and waves hello with the right hand.'),
          (90, 'A person stands relaxed and lowers the hand.'), frames=150, kind='action', jobs=ANY),
        C('BowGreet', (0, 'A person stands and bows politely from the waist.'),
          (75, 'A person straightens up and stands relaxed.'), frames=150, kind='action', jobs=ANY),
        C('PointDirections', 'A person stands and points into the distance with the right arm, giving directions.',
          'A person stands and gestures to the left, explaining the way.', kind='action', jobs=ANY),
        C('Shrug', (0, 'A person stands and shrugs with both palms up.'),
          (90, 'A person stands and shakes the head, shrugging again.'), frames=180, kind='action', jobs=ANY),
        C('Haggle', (0, 'A person stands bargaining, holding up fingers to show a price.'),
          (90, 'A person stands and shakes the head, waving a hand in refusal.'),
          (170, 'A person stands and nods, agreeing to a deal.'), kind='action', jobs=('merchant', 'customer')),
        C('CheerClap', 'A person stands and claps the hands enthusiastically.',
          'A person stands and cheers, raising both fists in the air.', kind='action', jobs=ANY),
    ]),
    ('Market', 'Stall keepers selling and customers buying', [
        C('BeckonCustomers', 'A person stands and waves customers over with one hand, beckoning.',
          'A person stands and gestures toward a table of goods.', jobs=('stall keeper', 'merchant')),
        C('HawkWares', 'A person stands and calls out loudly, cupping a hand beside the mouth.',
          'A person stands and holds up an item with one hand, showing it off.', props=('produce',),
          jobs=('stall keeper',)),
        C('PresentGoods', 'A person stands and holds an object out in front with both hands, presenting it to a customer.',
          kind='action', props=('goods',), jobs=('stall keeper', 'tailor', 'potter')),
        C('CountCoins', 'A person stands counting coins from one palm into the other hand.', props=('coins',),
          jobs=('stall keeper', 'tavern keeper', 'merchant')),
        C('InspectItem', 'A person stands turning a small object over in both hands, inspecting it closely.',
          props=('small item',), jobs=('customer', 'merchant')),
        C('WeighGoods', 'A person holds the left hand up in front of the chest, palm up, as if holding a scale.',
          'A person picks something up with the right hand and places it onto the left palm.',
          'A person bounces the left hand up and down to weigh it, looking at it closely.',
          props=('balance scale',), jobs=('stall keeper', 'miller', 'herbalist'), rev=1),
        C('ArrangeStall', 'A person stands at a table, picking up items and arranging them neatly on the table.',
          jobs=('stall keeper', 'chandler', 'potter')),
        C('WipeCounter', 'A person stands wiping a table top with a cloth in circles.', props=('cloth',),
          jobs=('tavern keeper', 'stall keeper', 'baker')),
        C('BrowseStall', (0, 'A person stands at a market table, looking over the goods.'),
          (100, 'A person picks up an item from the table and examines it.'),
          (180, 'A person puts the item back down on the table.'), kind='action', jobs=('customer',)),
        C('PayCoins', (0, 'A person takes a coin pouch from the belt and opens it.'),
          (110, 'A person hands coins to someone in front of them.'),
          (180, 'A person ties the pouch back onto the belt.'), kind='action', props=('coin pouch',), jobs=('customer',)),
    ]),
    ('Woodwork', 'Woodcutters, carpenters, coopers and masons', [
        C('ChopWood', 'A person chops wood with an axe, raising it over the head with both hands and swinging it down onto a chopping block, again and again.',
          props=('axe',), jobs=('woodcutter', 'labourer')),
        C('SplitKindling', 'A person bends over a chopping block, splitting small pieces of wood with a hatchet in one hand.',
          props=('hatchet',), jobs=('woodcutter', 'tavern keeper', 'labourer')),
        C('SawPlank', 'A person saws a plank of wood on a sawhorse, pushing and pulling a hand saw back and forth.',
          props=('hand saw',), jobs=('carpenter', 'cooper')),
        C('HammerNails', 'A person stands at a workbench hammering nails into wood with one hand.',
          props=('hammer',), jobs=('carpenter', 'cooper')),
        C('PlaneWood', 'A person leans over a table and slides both hands forward along it in one long stroke.',
          'A person pulls both hands back toward the body and slides them forward again in a long stroke.',
          'A person leans over the table, pushing both hands forward in a long stroke and pulling them back.',
          props=('wood plane',), jobs=('carpenter', 'cooper'), rev=1),
        C('StackFirewood', 'A person bends down, picks up logs and stacks them onto a pile.', props=('log',),
          jobs=('woodcutter', 'labourer')),
        C('ChiselStone', 'A person stands carving stone with a chisel in one hand and a mallet in the other, tapping it repeatedly.',
          props=('chisel', 'mallet'), jobs=('mason',)),
        C('LayBricks', 'A person bends forward laying bricks, spreading mortar with a trowel and placing each brick.',
          props=('trowel', 'brick'), jobs=('mason',)),
        C('WhittleStanding', 'A person stands whittling a piece of wood with a small knife, shaving it away from the body.',
          props=('knife', 'stick'), jobs=ANY),
        C('CooperHoop', 'A person bends over a barrel, hammering the metal hoop down around it with a mallet.',
          props=('mallet',), jobs=('cooper',)),
    ]),
    ('Smithing', 'Smiths, armourers, tanners, potters and weavers', [
        C('ForgeAnvil', 'A blacksmith hammers metal on an anvil, raising a hammer with the right hand and striking down repeatedly.',
          props=('smith hammer', 'tongs'), jobs=('smith',)),
        C('ForgeBellows', 'A person pumps a large bellows, pushing a handle down with both hands and lifting it, repeatedly.',
          jobs=('smith',)),
        C('QuenchBlade', (0, 'A person holds tongs out in front with both hands.'),
          (90, 'A person bends and plunges the tongs down into a barrel of water.'),
          (170, 'A person lifts the tongs and inspects the end.'), kind='action', props=('tongs',), jobs=('smith',)),
        C('SharpenWhetstone', 'A person stands holding a blade in one hand, stroking a whetstone along its edge with the other hand.',
          props=('blade', 'whetstone'), jobs=('smith', 'guard', 'butcher')),
        C('SharpenGrindstone', 'A person stands bent forward, holding a blade with both hands against a spinning grindstone, sliding it back and forth.',
          props=('blade',), jobs=('smith',)),
        C('InspectBlade', 'A person holds a sword up with both hands and looks along the edge.',
          'A person turns the sword over and runs a thumb along the blade.', kind='action', props=('sword',),
          jobs=('smith', 'guard', 'customer')),
        C('PolishArmor', 'A person stands holding a helmet in one hand, polishing it with a cloth in the other.',
          props=('helmet', 'cloth'), jobs=('smith', 'guard')),
        C('ScrapeHide', 'A person stands leaning over a frame, scraping an animal hide with a blade held in both hands, pushing down repeatedly.',
          props=('scraper',), jobs=('tanner', 'butcher')),
        C('ShapeClay', 'A person bends over a table, shaping clay with both hands.', jobs=('potter',)),
        C('WorkLoom', 'A person stands at a loom, passing a shuttle across with one hand and pulling a beam toward the body with both hands.',
          props=('shuttle',), jobs=('weaver',)),
    ]),
    ('Farming', 'Fields, gardens, animals and the well', [
        C('DigShovel', 'A person stands with the feet planted and drives a shovel down into the ground with both hands.',
          'A person lifts the shovel full of soil and tosses it to the right side.',
          'A person drives the shovel down into the ground again with both hands.',
          props=('shovel',), jobs=('farmer', 'labourer', 'gravedigger'), rev=1),
        C('HoeSoil', 'A person hoes the soil, raising a hoe with both hands and chopping it down into the ground, staying in place.',
          props=('hoe',), jobs=('farmer', 'herbalist'), rev=1),
        C('RakeGround', 'A person rakes the ground, pulling a rake toward the body with both hands, repeatedly.',
          props=('rake',), jobs=('farmer', 'labourer')),
        C('ScytheHarvest', 'A person harvests grain with a scythe, swinging it low from right to left with both hands.',
          props=('scythe',), jobs=('farmer',)),
        C('SowSeeds', 'A person stands and scatters seeds from a bag at the hip, throwing handfuls out in an arc.',
          props=('seed bag',), jobs=('farmer',)),
        C('PullWeeds', 'A person crouches and pulls weeds out of the ground with both hands, tossing them aside.',
          jobs=('farmer', 'herbalist')),
        C('PitchforkHay', 'A person pitches hay with a pitchfork, scooping from the ground and tossing it up high onto a pile.',
          props=('pitchfork',), jobs=('farmer', 'carter')),
        C('FeedChickens', 'A person stands holding a bowl against the hip and scatters grain onto the ground with the other hand.',
          props=('bowl',), jobs=('farmer', 'baker')),
        C('DrawWaterWell', (0, 'A person pulls a rope hand over hand, raising a bucket from a well.'),
          (160, 'A person lifts the bucket with both hands and sets it down on the edge.'), kind='action',
          props=('bucket',), jobs=ANY),
        C('PickFruit', 'A person reaches up high into a tree to pick fruit and puts it into a basket at the side.',
          props=('fruit',), jobs=('farmer', 'herbalist')),
    ]),
    ('Household', 'Cooking, cleaning and laundry', [
        C('SweepBroom', 'A person sweeps the floor with a broom, brushing it from side to side with both hands.',
          props=('broom',), jobs=('sweeper', 'tavern keeper', 'servant')),
        C('ScrubFloor', 'A person kneels on the floor and scrubs it with a brush in both hands, moving it back and forth.',
          props=('scrub brush',), jobs=('servant', 'tavern keeper')),
        C('WashLaundry', 'A person kneels beside a tub, scrubbing clothes on a washboard with both hands.',
          props=('cloth',), jobs=('servant', 'anyone')),
        C('HangLaundry', 'A person reaches up and pins cloth onto a washing line, then picks up another piece from a basket on the ground.',
          props=('cloth',), jobs=('servant', 'anyone')),
        C('BeatRug', 'A person beats a hanging rug with a stick, swinging it hard with one hand, repeatedly.',
          props=('rug beater',), jobs=('servant', 'tavern keeper')),
        C('KneadDough', 'A person stands at a table kneading dough with both hands, pushing it forward and folding it back.',
          jobs=('baker',)),
        C('StirCauldron', 'A person stands stirring a large pot with a long ladle held in both hands, in circles.',
          props=('ladle',), jobs=('cook', 'tavern keeper', 'herbalist', 'chandler')),
        C('ChopVegetables', 'A person stands at a table chopping vegetables with a knife in the right hand, holding them with the left.',
          props=('knife',), jobs=('cook', 'tavern keeper', 'butcher')),
        C('ChurnButter', 'A person stands pumping a butter churn, pushing a pole up and down with both hands.',
          props=('churn pole',), jobs=('farmer', 'cook')),
        C('GrindMortar', 'A person stands holding a bowl against the body with one arm and grinding with a pestle in the other hand.',
          props=('mortar', 'pestle'), jobs=('herbalist', 'cook', 'baker')),
    ]),
    ('Hauling', 'Porters, carters and dock workers', [
        C('LiftCrate', (0, 'A person bends at the knees and lifts a heavy crate from the ground with both hands.'),
          (120, 'A person sets the heavy crate back down on the ground.'), kind='action', props=('crate',),
          jobs=('porter', 'carter', 'labourer')),
        C('ShoulderSack', 'A person holds a heavy sack on the right shoulder with both hands, bouncing it to settle the weight.',
          'A person shifts the heavy sack on the shoulder and steps from foot to foot.',
          'A person adjusts the grip on the heavy sack on the right shoulder with both hands.',
          props=('sack',), jobs=('porter', 'miller', 'carter'), rev=1, still=True),
        C('LoadCart', (0, 'A person lifts a heavy sack from the ground with both arms.'),
          (110, 'A person heaves the sack up onto a high cart in front of them.'), kind='action', props=('sack',),
          jobs=('porter', 'carter', 'miller')),
        C('HaulRope', 'A person grabs a rope in front of them with both hands and pulls it hard toward the chest, leaning back.',
          'A person reaches forward with both hands and pulls the rope hard again, leaning back.',
          'A person reaches forward and pulls the rope hard toward the chest once more.', props=('rope',),
          jobs=('dock worker', 'labourer', 'fisher'), rev=1),
        C('StackCrates', (0, 'A person picks up a box from the ground.'),
          (100, 'A person lifts the box up and places it on top of a high stack.'), kind='action', props=('box',),
          jobs=('porter', 'dock worker', 'chandler')),
        C('HandOverLoad', (0, 'A person stands holding a heavy box in both arms against the stomach.'),
          (90, 'A person reaches forward with both arms, holding out the box to someone in front.'),
          (170, 'A person lowers the empty arms back to the sides.'), kind='action', props=('box',),
          jobs=('porter', 'carter'), rev=1),
        C('CatchBreath', (0, 'A person bends forward with hands on the knees, breathing hard, tired.'),
          (130, 'A person straightens up and wipes the forehead with the back of the hand.'), kind='action',
          jobs=('porter', 'labourer', 'anyone')),
        C('RubSoreBack', (0, 'A person stands and puts both hands on the lower back.'),
          (60, 'A person bends backward, stretching, with both hands pressing the lower back.'),
          (140, 'A person straightens up and rubs the lower back with one hand.'),
          (200, 'A person stands relaxed with arms at the sides.'),
          kind='action', jobs=('porter', 'farmer', 'labourer'), rev=1),
        C('ShovelCoal', 'A person shovels coal from a pile, scooping and tossing it forward into a furnace.',
          props=('shovel',), jobs=('smith', 'baker', 'labourer')),
        C('CastNet', (0, 'A person swings a fishing net back with both hands.'),
          (80, 'A person throws the net out forward in a wide arc.'),
          (150, 'A person pulls the net back in hand over hand.'), kind='action', props=('net',), jobs=('fisher',)),
    ]),
    ('Guard', 'Town guard and soldiers on watch and drilling', [
        C('Attention', 'A soldier stands at attention with the feet together, back straight and chin up, the right hand holding a spear upright at the side.',
          props=('spear',), jobs=('guard',), rev=1, still=True),
        C('WatchLookAround', 'A guard stands on watch holding a spear upright, slowly turning the head to scan the surroundings.',
          props=('spear',), jobs=('guard',), still=True),
        C('LeanOnSpear', 'A bored guard stands with the feet together, leaning sideways on a tall spear planted beside them, both hands on the shaft.',
          'A bored guard leans on the spear and shifts weight from one leg to the other.',
          props=('spear',), jobs=('guard',), rev=1),
        C('Salute', (0, 'A soldier stands and salutes, bringing a fist to the chest.'),
          (80, 'A soldier lowers the arm and stands at attention.'), frames=150, kind='action', jobs=('guard',)),
        C('Halt', (0, 'A guard raises one palm forward, ordering someone to stop.'),
          (90, 'A guard points sternly at someone in front of them.'), frames=180, kind='action', jobs=('guard',)),
        C('SwordDrill', (0, 'A soldier practices sword strikes, slashing diagonally downward with both hands.'),
          (80, 'A soldier practices a horizontal sword slash.'),
          (160, 'A soldier thrusts a sword forward, then returns to a guard stance.'), props=('sword',), jobs=('guard',)),
        C('ShieldDrill', 'A soldier holds a shield up on the left arm and raises it to block, then lowers it, repeatedly.',
          props=('shield', 'sword'), jobs=('guard',)),
        C('DrawSheathe', (0, 'A soldier draws a sword from the left hip with the right hand.'),
          (90, 'A soldier holds the sword up and looks at it.'),
          (170, 'A soldier puts the sword back into the sheath at the left hip.'), kind='action', props=('sword',),
          jobs=('guard',)),
        C('BoredStretch', (0, 'A guard yawns and stretches the arms up.'),
          (120, 'A guard rolls the shoulders and stretches the neck, then stands upright.'), kind='action', jobs=('guard',)),
        C('GiveOrders', (0, 'A commander stands pointing to the left, giving orders.'),
          (100, 'A commander gestures forward with the whole arm, commanding.'),
          (180, 'A commander stands with hands on hips.'), kind='action', jobs=('guard captain',)),
    ]),
    ('Tavern', 'Drinking, eating, music and dancing', [
        C('DrinkMug', (0, 'A person stands holding a mug and takes a long drink from it.'),
          (130, 'A person lowers the mug and wipes the mouth with the back of the hand.'), props=('mug',), jobs=ANY),
        C('ToastCheers', (0, 'A person raises a mug high in a toast.'),
          (90, 'A person clinks the mug forward and drinks.'), frames=180, kind='action', props=('mug',), jobs=ANY),
        C('DrunkSway', 'A drunk person sways from side to side, almost falling over to the left.',
          'A drunk person staggers, throwing the arms out to catch their balance.',
          'A drunk person sways forward and back with the head drooping.', jobs=('drunk',), rev=1),
        C('EatStanding', 'A person stands eating bread held in one hand, taking bites and chewing.', props=('bread',),
          jobs=ANY),
        C('DanceJig', 'A person dances a lively folk jig in place, hopping and kicking the feet, arms swinging.',
          jobs=('reveller', 'musician')),
        C('DanceClapSpin', 'A person dances in place, clapping the hands above the head.',
          'A person turns around in a circle while dancing.', jobs=('reveller',)),
        C('PlayLute', 'A person stands playing a lute, holding the neck with the left hand and strumming with the right hand, swaying to the music.',
          props=('lute',), jobs=('musician',)),
        C('PlayFlute', 'A person stands playing a flute held to the right side of the mouth with both hands, swaying gently.',
          props=('flute',), jobs=('musician',)),
        C('PlayDrum', 'A person beats a drum at the left hip, swinging the right forearm down hard to strike it, again and again.',
          'A person keeps striking the drum at the hip with the right hand in a fast rhythm, nodding along.',
          props=('drum',), jobs=('musician',), rev=1),
        C('Juggle', 'A person stands juggling balls, tossing them up and catching them with both hands.',
          props=('balls',), jobs=('entertainer',)),
    ]),
    ('Seated', 'On a bench, stool or the ground (place on a seat at runtime)', [
        C('SitIdle', 'A person sits on a bench, relaxed, hands resting on the knees, looking around.', jobs=ANY, still=True),
        C('SitTalk', 'A person sits on a bench, talking and moving the right hand while explaining.',
          'A person sits, turns toward someone at the side and opens both hands while talking.',
          'A person sits and laughs, slapping one knee with the hand.', jobs=ANY, rev=1),
        C('SitEat', 'A person sits at a table eating with a spoon from a bowl.', props=('spoon', 'bowl'), jobs=ANY),
        C('SitDrink', (0, 'A person sits on a stool and drinks from a mug.'),
          (130, 'A person sits and sets the mug down on the table.'), props=('mug',), jobs=ANY),
        C('SitWhittle', 'A person sits on a stool whittling a piece of wood with a knife.', props=('knife', 'stick'),
          jobs=ANY),
        C('SitSew', 'A person sits sewing cloth on the lap, pulling a needle and thread up with the right hand.',
          props=('needle', 'cloth'), jobs=('tailor', 'weaver')),
        C('SitRead', (0, 'A person sits holding an open book in both hands in front of the chest, reading.'),
          (100, 'A person sits and sweeps the right hand across from right to left, turning a page.'),
          (160, 'A person sits reading the open book held in both hands, tilting the head.'), props=('book',),
          jobs=('scholar', 'priest', 'merchant'), rev=1),
        C('SitWrite', 'A person sits at a desk writing with a quill, dipping it in ink.', props=('quill',),
          jobs=('scribe', 'merchant')),
        C('SitDoze', (0, 'A person sits on a bench, the head slowly sinking forward onto the chest as they fall asleep.'),
          (120, 'A person sits and suddenly jerks the head up, waking with a start.'),
          (170, 'A person sits and the head slowly sinks forward again, dozing.'), jobs=('guard', 'anyone'), rev=1),
        C('SitGround', 'A person sits on the ground with the legs crossed, resting, hands on the knees.', jobs=ANY, still=True),
    ]),
    ('StreetLife', 'Faith, beggars, the crier, moods and the sick', [
        C('PrayKneel', 'A person kneels on the ground with hands clasped together in prayer, head bowed.',
          jobs=('priest', 'anyone'), still=True),
        C('PrayStand', 'A person stands with hands pressed together in prayer, head bowed.', jobs=('priest', 'anyone'), still=True),
        C('BegAlms', 'A beggar kneels on the ground holding out a cupped hand, pleading to passersby.', props=('bowl',),
          jobs=('beggar',)),
        C('GrieveCry', 'A person stands crying, covering the face with both hands, shoulders shaking.', jobs=('mourner',)),
        C('NervousWait', 'A nervous person rubs the hands together quickly in front of the chest.',
          'A nervous person looks over the left shoulder and then over the right shoulder.',
          'A nervous person shifts from foot to foot, wringing the hands.', jobs=ANY, rev=1),
        C('CoughSick', 'A sick person stands hunched, coughing into one hand.', jobs=('sick',)),
        C('WarmHandsFire', 'A person crouches and holds both hands out toward a fire, rubbing them together to warm them.',
          jobs=ANY),
        C('TownCrier', 'A town crier stands holding an unrolled scroll with both hands, reading it out loud.',
          'A town crier raises one arm and calls out loudly.', props=('scroll',), jobs=('crier',)),
        C('ReadNotice', 'A person stands looking up at a notice on a wall, reading it, one hand on the chin.', jobs=ANY),
        C('SleepGround', 'A person lies on the ground on their side, asleep, breathing slowly.',
          jobs=('beggar', 'drunk'), still=True),
    ]),
]

ROOT = '/Game/Animation/KimodoTests/AmbientLibrary'
GEN = ROOT + '/_Generation'
GAP = 15


def folder(ci):
    return '%s/%02d_%s' % (ROOT, ci + 1, CATEGORIES[ci][0])


def seq_path(ci):
    return '%s/LS_Amb_%02d_%s' % (GEN, ci + 1, CATEGORIES[ci][0])


def asset_name(ci, clip):
    return 'AS_Amb_%s_%s' % (CATEGORIES[ci][0], clip['id'])


def layout(ci):
    """[(clip, start frame in the category's generation sequence, seed)]"""
    out, t = [], 0
    for k, clip in enumerate(CATEGORIES[ci][2]):
        out.append((clip, t, SEED_BASE + 100 * (ci + 1) + k + 10000 * clip['rev']))
        t += clip['frames'] + GAP
    return out


def pending_redo():
    """{(category, clip id)} of clips parked in PENDING_REDO.md (headings like '## 02 Social / TalkCasual')."""
    import os
    import re
    fn = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PENDING_REDO.md')
    if not os.path.exists(fn):
        return set()
    return {(m.group(1), m.group(2)) for m in re.finditer(r'^## \d\d (\w+) / (\w+)', open(fn, encoding='utf-8').read(), re.M)}


def total():
    return sum(len(c[2]) for c in CATEGORIES)


if __name__ == '__main__':
    ids = set()
    for ci, (name, _d, clips) in enumerate(CATEGORIES):
        for clip in clips:
            key = (name, clip['id'])
            assert key not in ids, key
            ids.add(key)
            assert clip['prompts'][0][0] == 0, key
            assert all(0 <= o < clip['frames'] for o, _s in clip['prompts']), key
        print('%02d %-11s %2d clips  %5.1f s' % (ci + 1, name, len(clips), sum(c['frames'] for c in clips) / FPS))
    prompts = {s for c in CATEGORIES for clip in c[2] for _o, s in clip['prompts']}
    print('total %d clips, %d distinct prompts, %.1f min' % (total(), len(prompts),
          sum(clip['frames'] for c in CATEGORIES for clip in c[2]) / FPS / 60))
