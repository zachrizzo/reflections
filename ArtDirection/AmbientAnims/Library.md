# Ambient NPC animation library

Generated with UE 5.9 Kimodo (model `nvidia/Kimodo-SOMA-RP-v1.1`, licensed for commercial use) on a MetaHuman (BP_Kellan, `/Game/MetaHumans/Common` `metahuman_base_skel`), then baked in place (no root motion) to one AnimSequence per clip.

- 124 clips in 12 categories, 124 baked and reviewed.
- Assets: `/Game/Animation/KimodoTests/AmbientLibrary/<NN>_<Category>/AS_Amb_<Category>_<Clip>`.
- Generation sequences (re-generate or tweak a take there): `/Game/Animation/KimodoTests/AmbientLibrary/_Generation/LS_Amb_<NN>_<Category>`.
- Source of truth for prompts, props and jobs: `Tools/AmbientAnims/ambient_catalog.py`. Each baked clip also carries this data as asset metadata (`Ambient.*`, `Kimodo.*` tags).
- Review sheets (stick figures every ~1 s, plus scores): `Saved/KimodoAmbient/sheets/`.

**Kinds.** `loop`: a repeating activity. Clips do not loop seamlessly; chain takes with a 0.3-0.5 s crossfade. `action`: a one-shot beat that starts and ends near a relaxed stand.

**Props.** Kimodo is not prop-aware and the SOMA body has no fingers, so hands stay open. Attach the prop to the `hand_r` / `hand_l` socket at runtime; some grips will need a per-clip offset.

**Seated clips** sit on an invisible seat at the default seat height. Place the NPC on a bench or stool.

**Flags.** FROZEN? = the prompt asked for an action but the take is a held pose; SLIDE = a planted foot skates (over 25 cm/s); SEAM = a loop ends over 20 cm from its start. Clips meant to be a quiet held pose (standing guard, dozing on the ground) are marked *held pose* and never flagged FROZEN?. *Redo queued* means a better prompt is parked in `Tools/AmbientAnims/PENDING_REDO.md`; the current take is usable as a placeholder.

## 01 Idle

Standing idles: what anyone does while waiting or between tasks.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Idle_Relaxed` | loop | 8.0 s | - | anyone | 0: A person stands relaxed with arms at the sides, breathing calmly and shifting weight slightly. | energy 2, slide 2, *held pose* |
| `AS_Amb_Idle_WeightShift` | loop | 8.0 s | - | anyone | 0: A person stands and shifts their weight onto the left leg, the hips swaying to the left.<br>80: A person shifts their weight onto the right leg, the hips swaying to the right.<br>160: A person shifts their weight back onto the left leg and glances to the side. | energy 2, slide 4, **FROZEN?**, *redo queued* |
| `AS_Amb_Idle_LookAround` | loop | 8.0 s | - | anyone | 0: A person stands still and looks slowly to the left.<br>90: A person stands still and looks slowly to the right.<br>170: A person stands relaxed and looks straight ahead. | energy 1, slide 2, *held pose* |
| `AS_Amb_Idle_ArmsCrossed` | loop | 8.0 s | - | anyone | 0: A person stands with arms crossed over the chest, shifting weight and looking around. | energy 2, slide 2, *held pose* |
| `AS_Amb_Idle_HandsOnHips` | loop | 8.0 s | - | anyone | 0: A person stands with both hands on the hips, looking around. | energy 1, slide 2, *held pose* |
| `AS_Amb_Idle_HandsBehindBack` | loop | 8.0 s | - | guard, merchant, noble | 0: A person stands upright with hands clasped behind the back, rocking slightly on the heels. | energy 2, slide 2, *held pose* |
| `AS_Amb_Idle_Stretch` | action | 8.0 s | - | anyone | 0: A person stands and stretches both arms high above the head.<br>100: A person stands and twists the torso from side to side, stretching.<br>180: A person stands relaxed with arms at the sides. | energy 14, slide 3 |
| `AS_Amb_Idle_Yawn` | action | 8.0 s | - | anyone | 0: A person stands and yawns, covering the mouth with one hand.<br>110: A person stands and rubs the eyes, tired.<br>170: A person stands relaxed, shifting weight. | energy 13, slide 2 |
| `AS_Amb_Idle_ScratchHead` | action | 8.0 s | - | anyone | 0: A person stands and scratches the back of the head, puzzled.<br>120: A person stands with one hand on the chin, thinking. | energy 14, slide 2 |
| `AS_Amb_Idle_ShadeEyes` | action | 8.0 s | - | guard, fisher, farmer | 0: A person stands and raises one hand to shade the eyes, looking far into the distance.<br>150: A person stands and lowers the hand, relaxed. | energy 7, slide 2 |
| `AS_Amb_Idle_Impatient` | loop | 8.0 s | - | anyone | 0: A person stands and taps the right foot on the ground again and again, impatient.<br>80: A person puts both hands on the hips, sighs and looks to the left and the right.<br>160: A person drops the hands to the sides and taps the right foot again and again. | energy 5, slide 6 |
| `AS_Amb_Idle_Cold` | loop | 8.0 s | - | anyone | 0: A person stands hunched against the cold, rubbing the upper arms with both hands and stamping the feet. | energy 8, slide 2 |

## 02 Social

Talking, listening and reacting to someone standing in front.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Social_TalkCasual` | loop | 8.0 s | - | anyone | 0: A person talks to someone in front of them, moving the right hand up and down while explaining.<br>80: A person talks, opening both hands outward, palms up.<br>160: A person talks, lowering the hands and nodding, then lifting the right hand again. | energy 1, slide 2, **FROZEN?**, *redo queued* |
| `AS_Amb_Social_TalkAnimated` | loop | 8.0 s | - | anyone | 0: A person stands telling an exciting story, gesturing widely with both arms.<br>120: A person stands talking excitedly, pointing and waving the arms. | energy 15, slide 2 |
| `AS_Amb_Social_ListenNod` | loop | 8.0 s | - | anyone | 0: A person stands listening to someone in front of them, nodding, arms relaxed. | energy 5, slide 2, *held pose* |
| `AS_Amb_Social_Laugh` | action | 8.0 s | - | anyone | 0: A person stands and laughs loudly, leaning back.<br>100: A person stands laughing and slaps the thigh.<br>180: A person stands smiling, relaxed. | energy 12, slide 3 |
| `AS_Amb_Social_Argue` | loop | 8.0 s | - | anyone | 0: A person stands arguing angrily with someone in front of them, pointing a finger.<br>100: A person stands arguing, throwing both hands up in frustration.<br>180: A person stands angrily with arms crossed. | energy 12, slide 3 |
| `AS_Amb_Social_WhisperGossip` | action | 8.0 s | - | anyone | 0: A person leans in and whispers to someone beside them, a hand raised to the mouth.<br>130: A person stands upright and glances around secretively. | energy 4, slide 2 |
| `AS_Amb_Social_WaveGreet` | action | 5.0 s | - | anyone | 0: A person stands and waves hello with the right hand.<br>90: A person stands relaxed and lowers the hand. | energy 9, slide 2 |
| `AS_Amb_Social_BowGreet` | action | 5.0 s | - | anyone | 0: A person stands and bows politely from the waist.<br>75: A person straightens up and stands relaxed. | energy 10, slide 5 |
| `AS_Amb_Social_PointDirections` | action | 8.0 s | - | anyone | 0: A person stands and points into the distance with the right arm, giving directions.<br>120: A person stands and gestures to the left, explaining the way. | energy 8, slide 2 |
| `AS_Amb_Social_Shrug` | action | 6.0 s | - | anyone | 0: A person stands and shrugs with both palms up.<br>90: A person stands and shakes the head, shrugging again. | energy 12, slide 2 |
| `AS_Amb_Social_Haggle` | action | 8.0 s | - | merchant, customer | 0: A person stands bargaining, holding up fingers to show a price.<br>90: A person stands and shakes the head, waving a hand in refusal.<br>170: A person stands and nods, agreeing to a deal. | energy 6, slide 2 |
| `AS_Amb_Social_CheerClap` | action | 8.0 s | - | anyone | 0: A person stands and claps the hands enthusiastically.<br>120: A person stands and cheers, raising both fists in the air. | energy 31, slide 4 |

## 03 Market

Stall keepers selling and customers buying.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Market_BeckonCustomers` | loop | 8.0 s | - | stall keeper, merchant | 0: A person stands and waves customers over with one hand, beckoning.<br>120: A person stands and gestures toward a table of goods. | energy 17, slide 2 |
| `AS_Amb_Market_HawkWares` | loop | 8.0 s | produce | stall keeper | 0: A person stands and calls out loudly, cupping a hand beside the mouth.<br>120: A person stands and holds up an item with one hand, showing it off. | energy 10, slide 4 |
| `AS_Amb_Market_PresentGoods` | action | 8.0 s | goods | stall keeper, tailor, potter | 0: A person stands and holds an object out in front with both hands, presenting it to a customer. | energy 7, slide 2 |
| `AS_Amb_Market_CountCoins` | loop | 8.0 s | coins | stall keeper, tavern keeper, merchant | 0: A person stands counting coins from one palm into the other hand. | energy 4, slide 2 |
| `AS_Amb_Market_InspectItem` | loop | 8.0 s | small item | customer, merchant | 0: A person stands turning a small object over in both hands, inspecting it closely. | energy 6, slide 2 |
| `AS_Amb_Market_WeighGoods` | loop | 8.0 s | balance scale | stall keeper, miller, herbalist | 0: A person holds the left hand up in front of the chest, palm up, as if holding a scale.<br>80: A person picks something up with the right hand and places it onto the left palm.<br>160: A person bounces the left hand up and down to weigh it, looking at it closely. | energy 7, slide 2 |
| `AS_Amb_Market_ArrangeStall` | loop | 8.0 s | - | stall keeper, chandler, potter | 0: A person stands at a table, picking up items and arranging them neatly on the table. | energy 6, slide 2 |
| `AS_Amb_Market_WipeCounter` | loop | 8.0 s | cloth | tavern keeper, stall keeper, baker | 0: A person stands wiping a table top with a cloth in circles. | energy 6, slide 2 |
| `AS_Amb_Market_BrowseStall` | action | 8.0 s | - | customer | 0: A person stands at a market table, looking over the goods.<br>100: A person picks up an item from the table and examines it.<br>180: A person puts the item back down on the table. | energy 5, slide 3 |
| `AS_Amb_Market_PayCoins` | action | 8.0 s | coin pouch | customer | 0: A person takes a coin pouch from the belt and opens it.<br>110: A person hands coins to someone in front of them.<br>180: A person ties the pouch back onto the belt. | energy 7, slide 2 |

## 04 Woodwork

Woodcutters, carpenters, coopers and masons.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Woodwork_ChopWood` | loop | 8.0 s | axe | woodcutter, labourer | 0: A person chops wood with an axe, raising it over the head with both hands and swinging it down onto a chopping block, again and again. | energy 26, slide 8 |
| `AS_Amb_Woodwork_SplitKindling` | loop | 8.0 s | hatchet | woodcutter, tavern keeper, labourer | 0: A person bends over a chopping block, splitting small pieces of wood with a hatchet in one hand. | energy 25, slide 10 |
| `AS_Amb_Woodwork_SawPlank` | loop | 8.0 s | hand saw | carpenter, cooper | 0: A person saws a plank of wood on a sawhorse, pushing and pulling a hand saw back and forth. | energy 28, slide 5 |
| `AS_Amb_Woodwork_HammerNails` | loop | 8.0 s | hammer | carpenter, cooper | 0: A person stands at a workbench hammering nails into wood with one hand. | energy 9, slide 2 |
| `AS_Amb_Woodwork_PlaneWood` | loop | 8.0 s | wood plane | carpenter, cooper | 0: A person leans over a table and slides both hands forward along it in one long stroke.<br>80: A person pulls both hands back toward the body and slides them forward again in a long stroke.<br>160: A person leans over the table, pushing both hands forward in a long stroke and pulling them back. | energy 13, slide 3 |
| `AS_Amb_Woodwork_StackFirewood` | loop | 8.0 s | log | woodcutter, labourer | 0: A person bends down, picks up logs and stacks them onto a pile. | energy 17, slide 5 |
| `AS_Amb_Woodwork_ChiselStone` | loop | 8.0 s | chisel, mallet | mason | 0: A person stands carving stone with a chisel in one hand and a mallet in the other, tapping it repeatedly. | energy 9, slide 2 |
| `AS_Amb_Woodwork_LayBricks` | loop | 8.0 s | trowel, brick | mason | 0: A person bends forward laying bricks, spreading mortar with a trowel and placing each brick. | energy 13, slide 2 |
| `AS_Amb_Woodwork_WhittleStanding` | loop | 8.0 s | knife, stick | anyone | 0: A person stands whittling a piece of wood with a small knife, shaving it away from the body. | energy 9, slide 2 |
| `AS_Amb_Woodwork_CooperHoop` | loop | 8.0 s | mallet | cooper | 0: A person bends over a barrel, hammering the metal hoop down around it with a mallet. | energy 13, slide 6 |

## 05 Smithing

Smiths, armourers, tanners, potters and weavers.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Smithing_ForgeAnvil` | loop | 8.0 s | smith hammer, tongs | smith | 0: A blacksmith hammers metal on an anvil, raising a hammer with the right hand and striking down repeatedly. | energy 10, slide 3 |
| `AS_Amb_Smithing_ForgeBellows` | loop | 8.0 s | - | smith | 0: A person pumps a large bellows, pushing a handle down with both hands and lifting it, repeatedly. | energy 14, slide 13 |
| `AS_Amb_Smithing_QuenchBlade` | action | 8.0 s | tongs | smith | 0: A person holds tongs out in front with both hands.<br>90: A person bends and plunges the tongs down into a barrel of water.<br>170: A person lifts the tongs and inspects the end. | energy 6, slide 3 |
| `AS_Amb_Smithing_SharpenWhetstone` | loop | 8.0 s | blade, whetstone | smith, guard, butcher | 0: A person stands holding a blade in one hand, stroking a whetstone along its edge with the other hand. | energy 9, slide 2 |
| `AS_Amb_Smithing_SharpenGrindstone` | loop | 8.0 s | blade | smith | 0: A person stands bent forward, holding a blade with both hands against a spinning grindstone, sliding it back and forth. | energy 14, slide 2 |
| `AS_Amb_Smithing_InspectBlade` | action | 8.0 s | sword | smith, guard, customer | 0: A person holds a sword up with both hands and looks along the edge.<br>120: A person turns the sword over and runs a thumb along the blade. | energy 3, slide 2, **FROZEN?**, *redo queued* |
| `AS_Amb_Smithing_PolishArmor` | loop | 8.0 s | helmet, cloth | smith, guard | 0: A person stands holding a helmet in one hand, polishing it with a cloth in the other. | energy 4, slide 2 |
| `AS_Amb_Smithing_ScrapeHide` | loop | 8.0 s | scraper | tanner, butcher | 0: A person stands leaning over a frame, scraping an animal hide with a blade held in both hands, pushing down repeatedly. | energy 6, slide 2 |
| `AS_Amb_Smithing_ShapeClay` | loop | 8.0 s | - | potter | 0: A person bends over a table, shaping clay with both hands. | energy 4, slide 2 |
| `AS_Amb_Smithing_WorkLoom` | loop | 8.0 s | shuttle | weaver | 0: A person stands at a loom, passing a shuttle across with one hand and pulling a beam toward the body with both hands. | energy 18, slide 2 |

## 06 Farming

Fields, gardens, animals and the well.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Farming_DigShovel` | loop | 8.0 s | shovel | farmer, labourer, gravedigger | 0: A person stands with the feet planted and drives a shovel down into the ground with both hands.<br>80: A person lifts the shovel full of soil and tosses it to the right side.<br>160: A person drives the shovel down into the ground again with both hands. | energy 32, slide 14 |
| `AS_Amb_Farming_HoeSoil` | loop | 8.0 s | hoe | farmer, herbalist | 0: A person hoes the soil, raising a hoe with both hands and chopping it down into the ground, staying in place. | energy 20, slide 4 |
| `AS_Amb_Farming_RakeGround` | loop | 8.0 s | rake | farmer, labourer | 0: A person rakes the ground, pulling a rake toward the body with both hands, repeatedly. | energy 18, slide 3 |
| `AS_Amb_Farming_ScytheHarvest` | loop | 8.0 s | scythe | farmer | 0: A person harvests grain with a scythe, swinging it low from right to left with both hands. | energy 8, slide 2 |
| `AS_Amb_Farming_SowSeeds` | loop | 8.0 s | seed bag | farmer | 0: A person stands and scatters seeds from a bag at the hip, throwing handfuls out in an arc. | energy 8, slide 2 |
| `AS_Amb_Farming_PullWeeds` | loop | 8.0 s | - | farmer, herbalist | 0: A person crouches and pulls weeds out of the ground with both hands, tossing them aside. | energy 14, slide 3 |
| `AS_Amb_Farming_PitchforkHay` | loop | 8.0 s | pitchfork | farmer, carter | 0: A person pitches hay with a pitchfork, scooping from the ground and tossing it up high onto a pile. | energy 12, slide 2 |
| `AS_Amb_Farming_FeedChickens` | loop | 8.0 s | bowl | farmer, baker | 0: A person stands holding a bowl against the hip and scatters grain onto the ground with the other hand. | energy 7, slide 2 |
| `AS_Amb_Farming_DrawWaterWell` | action | 8.0 s | bucket | anyone | 0: A person pulls a rope hand over hand, raising a bucket from a well.<br>160: A person lifts the bucket with both hands and sets it down on the edge. | energy 16, slide 3 |
| `AS_Amb_Farming_PickFruit` | loop | 8.0 s | fruit | farmer, herbalist | 0: A person reaches up high into a tree to pick fruit and puts it into a basket at the side. | energy 9, slide 2 |

## 07 Household

Cooking, cleaning and laundry.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Household_SweepBroom` | loop | 8.0 s | broom | sweeper, tavern keeper, servant | 0: A person sweeps the floor with a broom, brushing it from side to side with both hands. | energy 24, slide 2 |
| `AS_Amb_Household_ScrubFloor` | loop | 8.0 s | scrub brush | servant, tavern keeper | 0: A person kneels on the floor and scrubs it with a brush in both hands, moving it back and forth. | energy 15, slide 3 |
| `AS_Amb_Household_WashLaundry` | loop | 8.0 s | cloth | servant, anyone | 0: A person kneels beside a tub, scrubbing clothes on a washboard with both hands. | energy 7, slide 2 |
| `AS_Amb_Household_HangLaundry` | loop | 8.0 s | cloth | servant, anyone | 0: A person reaches up and pins cloth onto a washing line, then picks up another piece from a basket on the ground. | energy 8, slide 2 |
| `AS_Amb_Household_BeatRug` | loop | 8.0 s | rug beater | servant, tavern keeper | 0: A person beats a hanging rug with a stick, swinging it hard with one hand, repeatedly. | energy 12, slide 3 |
| `AS_Amb_Household_KneadDough` | loop | 8.0 s | - | baker | 0: A person stands at a table kneading dough with both hands, pushing it forward and folding it back. | energy 5, slide 2 |
| `AS_Amb_Household_StirCauldron` | loop | 8.0 s | ladle | cook, tavern keeper, herbalist, chandler | 0: A person stands stirring a large pot with a long ladle held in both hands, in circles. | energy 8, slide 2 |
| `AS_Amb_Household_ChopVegetables` | loop | 8.0 s | knife | cook, tavern keeper, butcher | 0: A person stands at a table chopping vegetables with a knife in the right hand, holding them with the left. | energy 5, slide 2 |
| `AS_Amb_Household_ChurnButter` | loop | 8.0 s | churn pole | farmer, cook | 0: A person stands pumping a butter churn, pushing a pole up and down with both hands. | energy 9, slide 2 |
| `AS_Amb_Household_GrindMortar` | loop | 8.0 s | mortar, pestle | herbalist, cook, baker | 0: A person stands holding a bowl against the body with one arm and grinding with a pestle in the other hand. | energy 6, slide 2 |

## 08 Hauling

Porters, carters and dock workers.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Hauling_LiftCrate` | action | 8.0 s | crate | porter, carter, labourer | 0: A person bends at the knees and lifts a heavy crate from the ground with both hands.<br>120: A person sets the heavy crate back down on the ground. | energy 25, slide 7 |
| `AS_Amb_Hauling_ShoulderSack` | loop | 8.0 s | sack | porter, miller, carter | 0: A person holds a heavy sack on the right shoulder with both hands, bouncing it to settle the weight.<br>80: A person shifts the heavy sack on the shoulder and steps from foot to foot.<br>160: A person adjusts the grip on the heavy sack on the right shoulder with both hands. | energy 2, slide 2, *held pose* |
| `AS_Amb_Hauling_LoadCart` | action | 8.0 s | sack | porter, carter, miller | 0: A person lifts a heavy sack from the ground with both arms.<br>110: A person heaves the sack up onto a high cart in front of them. | energy 22, slide 6 |
| `AS_Amb_Hauling_HaulRope` | loop | 8.0 s | rope | dock worker, labourer, fisher | 0: A person grabs a rope in front of them with both hands and pulls it hard toward the chest, leaning back.<br>80: A person reaches forward with both hands and pulls the rope hard again, leaning back.<br>160: A person reaches forward and pulls the rope hard toward the chest once more. | energy 12, slide 4 |
| `AS_Amb_Hauling_StackCrates` | action | 8.0 s | box | porter, dock worker, chandler | 0: A person picks up a box from the ground.<br>100: A person lifts the box up and places it on top of a high stack. | energy 19, slide 11 |
| `AS_Amb_Hauling_HandOverLoad` | action | 8.0 s | box | porter, carter | 0: A person stands holding a heavy box in both arms against the stomach.<br>90: A person reaches forward with both arms, holding out the box to someone in front.<br>170: A person lowers the empty arms back to the sides. | energy 3, slide 4, **FROZEN?**, *redo queued* |
| `AS_Amb_Hauling_CatchBreath` | action | 8.0 s | - | porter, labourer, anyone | 0: A person bends forward with hands on the knees, breathing hard, tired.<br>130: A person straightens up and wipes the forehead with the back of the hand. | energy 8, slide 2 |
| `AS_Amb_Hauling_RubSoreBack` | action | 8.0 s | - | porter, farmer, labourer | 0: A person stands and puts both hands on the lower back.<br>60: A person bends backward, stretching, with both hands pressing the lower back.<br>140: A person straightens up and rubs the lower back with one hand.<br>200: A person stands relaxed with arms at the sides. | energy 5, slide 3 |
| `AS_Amb_Hauling_ShovelCoal` | loop | 8.0 s | shovel | smith, baker, labourer | 0: A person shovels coal from a pile, scooping and tossing it forward into a furnace. | energy 8, slide 4 |
| `AS_Amb_Hauling_CastNet` | action | 8.0 s | net | fisher | 0: A person swings a fishing net back with both hands.<br>80: A person throws the net out forward in a wide arc.<br>150: A person pulls the net back in hand over hand. | energy 11, slide 2 |

## 09 Guard

Town guard and soldiers on watch and drilling.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Guard_Attention` | loop | 8.0 s | spear | guard | 0: A soldier stands at attention with the feet together, back straight and chin up, the right hand holding a spear upright at the side. | energy 1, slide 2, *held pose* |
| `AS_Amb_Guard_WatchLookAround` | loop | 8.0 s | spear | guard | 0: A guard stands on watch holding a spear upright, slowly turning the head to scan the surroundings. | energy 7, slide 2, *held pose* |
| `AS_Amb_Guard_LeanOnSpear` | loop | 8.0 s | spear | guard | 0: A bored guard stands with the feet together, leaning sideways on a tall spear planted beside them, both hands on the shaft.<br>120: A bored guard leans on the spear and shifts weight from one leg to the other. | energy 4, slide 2 |
| `AS_Amb_Guard_Salute` | action | 5.0 s | - | guard | 0: A soldier stands and salutes, bringing a fist to the chest.<br>80: A soldier lowers the arm and stands at attention. | energy 9, slide 2 |
| `AS_Amb_Guard_Halt` | action | 6.0 s | - | guard | 0: A guard raises one palm forward, ordering someone to stop.<br>90: A guard points sternly at someone in front of them. | energy 12, slide 2 |
| `AS_Amb_Guard_SwordDrill` | loop | 8.0 s | sword | guard | 0: A soldier practices sword strikes, slashing diagonally downward with both hands.<br>80: A soldier practices a horizontal sword slash.<br>160: A soldier thrusts a sword forward, then returns to a guard stance. | energy 15, slide 12 |
| `AS_Amb_Guard_ShieldDrill` | loop | 8.0 s | shield, sword | guard | 0: A soldier holds a shield up on the left arm and raises it to block, then lowers it, repeatedly. | energy 5, slide 2 |
| `AS_Amb_Guard_DrawSheathe` | action | 8.0 s | sword | guard | 0: A soldier draws a sword from the left hip with the right hand.<br>90: A soldier holds the sword up and looks at it.<br>170: A soldier puts the sword back into the sheath at the left hip. | energy 6, slide 2 |
| `AS_Amb_Guard_BoredStretch` | action | 8.0 s | - | guard | 0: A guard yawns and stretches the arms up.<br>120: A guard rolls the shoulders and stretches the neck, then stands upright. | energy 8, slide 2 |
| `AS_Amb_Guard_GiveOrders` | action | 8.0 s | - | guard captain | 0: A commander stands pointing to the left, giving orders.<br>100: A commander gestures forward with the whole arm, commanding.<br>180: A commander stands with hands on hips. | energy 8, slide 3 |

## 10 Tavern

Drinking, eating, music and dancing.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Tavern_DrinkMug` | loop | 8.0 s | mug | anyone | 0: A person stands holding a mug and takes a long drink from it.<br>130: A person lowers the mug and wipes the mouth with the back of the hand. | energy 9, slide 2 |
| `AS_Amb_Tavern_ToastCheers` | action | 6.0 s | mug | anyone | 0: A person raises a mug high in a toast.<br>90: A person clinks the mug forward and drinks. | energy 6, slide 2 |
| `AS_Amb_Tavern_DrunkSway` | loop | 8.0 s | - | drunk | 0: A drunk person sways from side to side, almost falling over to the left.<br>80: A drunk person staggers, throwing the arms out to catch their balance.<br>160: A drunk person sways forward and back with the head drooping. | energy 8, slide 3 |
| `AS_Amb_Tavern_EatStanding` | loop | 8.0 s | bread | anyone | 0: A person stands eating bread held in one hand, taking bites and chewing. | energy 4, slide 2 |
| `AS_Amb_Tavern_DanceJig` | loop | 8.0 s | - | reveller, musician | 0: A person dances a lively folk jig in place, hopping and kicking the feet, arms swinging. | energy 27, slide 36, **SLIDE**, *redo queued* |
| `AS_Amb_Tavern_DanceClapSpin` | loop | 8.0 s | - | reveller | 0: A person dances in place, clapping the hands above the head.<br>120: A person turns around in a circle while dancing. | energy 23, slide 24 |
| `AS_Amb_Tavern_PlayLute` | loop | 8.0 s | lute | musician | 0: A person stands playing a lute, holding the neck with the left hand and strumming with the right hand, swaying to the music. | energy 10, slide 2 |
| `AS_Amb_Tavern_PlayFlute` | loop | 8.0 s | flute | musician | 0: A person stands playing a flute held to the right side of the mouth with both hands, swaying gently. | energy 6, slide 2 |
| `AS_Amb_Tavern_PlayDrum` | loop | 8.0 s | drum | musician | 0: A person beats a drum at the left hip, swinging the right forearm down hard to strike it, again and again.<br>120: A person keeps striking the drum at the hip with the right hand in a fast rhythm, nodding along. | energy 12, slide 2 |
| `AS_Amb_Tavern_Juggle` | loop | 8.0 s | balls | entertainer | 0: A person stands juggling balls, tossing them up and catching them with both hands. | energy 8, slide 2 |

## 11 Seated

On a bench, stool or the ground (place on a seat at runtime).

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_Seated_SitIdle` | loop | 8.0 s | - | anyone | 0: A person sits on a bench, relaxed, hands resting on the knees, looking around. | energy 1, slide 2, *held pose* |
| `AS_Amb_Seated_SitTalk` | loop | 8.0 s | - | anyone | 0: A person sits on a bench, talking and moving the right hand while explaining.<br>80: A person sits, turns toward someone at the side and opens both hands while talking.<br>160: A person sits and laughs, slapping one knee with the hand. | energy 4, slide 3 |
| `AS_Amb_Seated_SitEat` | loop | 8.0 s | spoon, bowl | anyone | 0: A person sits at a table eating with a spoon from a bowl. | energy 3, slide 2 |
| `AS_Amb_Seated_SitDrink` | loop | 8.0 s | mug | anyone | 0: A person sits on a stool and drinks from a mug.<br>130: A person sits and sets the mug down on the table. | energy 3, slide 2 |
| `AS_Amb_Seated_SitWhittle` | loop | 8.0 s | knife, stick | anyone | 0: A person sits on a stool whittling a piece of wood with a knife. | energy 4, slide 2 |
| `AS_Amb_Seated_SitSew` | loop | 8.0 s | needle, cloth | tailor, weaver | 0: A person sits sewing cloth on the lap, pulling a needle and thread up with the right hand. | energy 7, slide 2 |
| `AS_Amb_Seated_SitRead` | loop | 8.0 s | book | scholar, priest, merchant | 0: A person sits holding an open book in both hands in front of the chest, reading.<br>100: A person sits and sweeps the right hand across from right to left, turning a page.<br>160: A person sits reading the open book held in both hands, tilting the head. | energy 3, slide 2 |
| `AS_Amb_Seated_SitWrite` | loop | 8.0 s | quill | scribe, merchant | 0: A person sits at a desk writing with a quill, dipping it in ink. | energy 5, slide 2 |
| `AS_Amb_Seated_SitDoze` | loop | 8.0 s | - | guard, anyone | 0: A person sits on a bench, the head slowly sinking forward onto the chest as they fall asleep.<br>120: A person sits and suddenly jerks the head up, waking with a start.<br>170: A person sits and the head slowly sinks forward again, dozing. | energy 5, slide 18, *redo queued* |
| `AS_Amb_Seated_SitGround` | loop | 8.0 s | - | anyone | 0: A person sits on the ground with the legs crossed, resting, hands on the knees. | energy 1, slide 2, *held pose* |

## 12 StreetLife

Faith, beggars, the crier, moods and the sick.

| Clip | Kind | Length | Props | Used by | Beats (frame: prompt) | Review |
|---|---|---|---|---|---|---|
| `AS_Amb_StreetLife_PrayKneel` | loop | 8.0 s | - | priest, anyone | 0: A person kneels on the ground with hands clasped together in prayer, head bowed. | energy 9, slide 4, *held pose* |
| `AS_Amb_StreetLife_PrayStand` | loop | 8.0 s | - | priest, anyone | 0: A person stands with hands pressed together in prayer, head bowed. | energy 8, slide 2, *held pose* |
| `AS_Amb_StreetLife_BegAlms` | loop | 8.0 s | bowl | beggar | 0: A beggar kneels on the ground holding out a cupped hand, pleading to passersby. | energy 16, slide 6 |
| `AS_Amb_StreetLife_GrieveCry` | loop | 8.0 s | - | mourner | 0: A person stands crying, covering the face with both hands, shoulders shaking. | energy 10, slide 2 |
| `AS_Amb_StreetLife_NervousWait` | loop | 8.0 s | - | anyone | 0: A nervous person rubs the hands together quickly in front of the chest.<br>80: A nervous person looks over the left shoulder and then over the right shoulder.<br>160: A nervous person shifts from foot to foot, wringing the hands. | energy 9, slide 2 |
| `AS_Amb_StreetLife_CoughSick` | loop | 8.0 s | - | sick | 0: A sick person stands hunched, coughing into one hand. | energy 12, slide 8 |
| `AS_Amb_StreetLife_WarmHandsFire` | loop | 8.0 s | - | anyone | 0: A person crouches and holds both hands out toward a fire, rubbing them together to warm them. | energy 9, slide 2 |
| `AS_Amb_StreetLife_TownCrier` | loop | 8.0 s | scroll | crier | 0: A town crier stands holding an unrolled scroll with both hands, reading it out loud.<br>120: A town crier raises one arm and calls out loudly. | energy 6, slide 2 |
| `AS_Amb_StreetLife_ReadNotice` | loop | 8.0 s | - | anyone | 0: A person stands looking up at a notice on a wall, reading it, one hand on the chin. | energy 7, slide 2 |
| `AS_Amb_StreetLife_SleepGround` | loop | 8.0 s | - | beggar, drunk | 0: A person lies on the ground on their side, asleep, breathing slowly. | energy 1, slide 2, *held pose* |
