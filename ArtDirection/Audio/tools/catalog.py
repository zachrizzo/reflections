"""Single source of truth for every jam sound: prompt, generation node, processing and cue settings, owner/event."""
import json, os

SFX_MODEL = "ElevenLabs Sound Effects v2 (eleven_text_to_sound_v2)"
MUS_MODEL = "ElevenLabs Music v2.5 (eleven_music_v2_5), instrumental"

# name, folder, node_id, prompt, gen_seconds, prompt_influence, loop, attenuation, class, cue volume, pitch range, owner, event
S = [
    # --- Spells (spell-combat-rebuild) ---
    ("Fire_Cast", "Spells", "KqCZRkXGjcbk5x7ttmQ0", "Burst of fire igniting from an open hand, sharp whoosh of flame with crackling embers, close-mic", 1.2, 0.5, False, "Medium", "SFX", 0.8, (0.95, 1.05), "spell", "Cast of a Fire-element spell (Fire Bolt, Flame Burst, Fireball)"),
    ("Fire_Impact", "Spells", "E3UXLDqvM7saBmjBm0Zj", "Fireball exploding on impact, deep punchy boom with roaring flames and crackling embers scattering", 1.8, 0.5, False, "Large", "SFX", 0.9, (0.94, 1.06), "spell", "Fire projectile hit / Flame Burst and Fireball area detonation"),
    ("Water_Cast", "Spells", "TrnduLAVYA4ROuouYS5W", "Swirling rush of water gathering and launching forward, splashy whoosh, close-mic", 1.2, 0.5, False, "Medium", "SFX", 0.8, (0.95, 1.05), "spell", "Cast of a Water-element spell (Water Bolt, Tidal Surge, Water Orb)"),
    ("Water_Impact", "Spells", "xrv6euQle3wmaH9Qqwwf", "Heavy blast of water slamming into stone, big splash with spray and dripping", 1.5, 0.5, False, "Medium", "SFX", 0.9, (0.94, 1.06), "spell", "Water projectile hit / Tidal Surge area"),
    ("Ice_Cast", "Spells", "6ZHTgizBazhvGqMtBFj8", "Ice crystals forming rapidly, crisp crackling freeze with a cold glassy shimmer", 1.2, 0.5, False, "Medium", "SFX", 0.8, (0.95, 1.05), "spell", "Cast of an Ice-element spell (Ice Shard, Frost Nova)"),
    ("Ice_Impact", "Spells", "QV8eiYwHMql82Ks7O7uC", "Ice shard shattering on impact, sharp glassy crack with tinkling frozen fragments", 1.3, 0.5, False, "Medium", "SFX", 0.9, (0.94, 1.06), "spell", "Ice Shard hit / Frost Nova burst"),
    ("Lightning_Cast", "Spells", "LEVm7B83MZSO8iNPmDaU", "Electric charge snapping in the air, crackling high-voltage arc zap", 1.0, 0.5, False, "Medium", "SFX", 0.75, (0.95, 1.05), "spell", "Cast of a Lightning spell (Lightning Burst, Lightning Bolt, Thunder Wave)"),
    ("Lightning_Impact", "Spells", "SL6rZRi2g8V9z0ZqOo87", "Lightning bolt striking the ground, loud sharp electric crack followed by a short rolling rumble", 2.0, 0.5, False, "Large", "SFX", 0.9, (0.95, 1.05), "spell", "Lightning hit / Thunder Wave area"),
    ("Earth_Cast", "Spells", "qHmCza98pMR8KQguThIo", "Stone and rock tearing up out of the ground, deep grinding rumble with falling gravel", 1.4, 0.5, False, "Medium", "SFX", 0.8, (0.95, 1.05), "spell", "Cast of an Earth spell (Stone Shard, Earth Shock)"),
    ("Earth_Impact", "Spells", "13NBrOyWWHVE3YJxbRuN", "Heavy boulder smashing into the ground, crunching thud with rock debris scattering", 1.6, 0.5, False, "Large", "SFX", 0.9, (0.94, 1.06), "spell", "Stone Shard hit / Earth Shock area"),
    ("Arcane_Cast", "Spells", "JmzUPKq3bmGnS4RlV9hM", "Mystical spell charging, shimmering resonant hum rising quickly into a soft magical whoosh", 1.2, 0.5, False, "Medium", "SFX", 0.8, (0.95, 1.05), "spell", "Cast of an Arcane spell (Arcane Bolt, Force Push)"),
    ("Arcane_Impact", "Spells", "w5uWapI8Hw79iIt9pl5v", "Burst of magical energy on impact, resonant crystalline pulse with a deep soft boom", 1.4, 0.5, False, "Medium", "SFX", 0.9, (0.94, 1.06), "spell", "Arcane Bolt hit / Force Push wave"),
    ("Heal_Shimmer", "Spells", "CLT13zN1MMqVculFHJsE", "Gentle healing magic, soft warm chimes and airy sparkling shimmer slowly rising", 2.5, 0.5, False, "Small", "SFX", 0.7, (0.97, 1.03), "spell", "Healing / Greater Heal / Healing Pulse cast (Life element)"),
    ("Shield_Up", "Spells", "HfYyEqhTTatXdS48Edwk", "Magical force barrier activating, deep resonant whoomp swelling into a humming glassy shimmer", 1.5, 0.5, False, "Small", "SFX", 0.8, (0.97, 1.03), "spell", "Arcane Shield (Ward) raised"),
    ("Shield_Block", "Spells", "oISovleCWCSgtAMth6a7", "Blow deflected by a magical energy barrier, resonant metallic ping with a buzzing ripple", 1.0, 0.5, False, "Small", "SFX", 0.85, (0.94, 1.06), "spell", "Damage absorbed by the Arcane Shield"),
    ("Shield_Loop", "Spells", "gs8czuaFGQ6QZ3YUES4Z", "Steady low hum of a magical force field, soft electric shimmer, constant", 4.0, 0.5, True, "Small", "SFX", 0.35, None, "spell", "Looping hum while the Arcane Shield is active (attach to caster, stop on expiry)"),
    ("Projectile_Loop", "Spells", "iymyfJEarcL35oDFArJs", "Magical projectile flying through the air, steady whooshing hum with faint sparkling crackle, constant", 3.0, 0.5, True, "Medium", "SFX", 0.5, None, "spell", "Looping in-flight sound attached to any spell projectile"),
    ("Levitation_Start", "Spells", "lrIsOJO8jsdOnPpW4ko9", "Gust of wind lifting upward with a soft airy magical whoosh", 1.5, 0.5, False, "Small", "SFX", 0.75, (0.96, 1.04), "spell", "Levitation (Air / Hover) cast"),
    ("Levitation_Loop", "Spells", "ksjt3fbj24vO2a4fC0tv", "Steady soft wind swirling around a person with a gentle magical hum, constant", 4.0, 0.5, True, "Small", "SFX", 0.4, None, "spell", "Looping wind while levitating"),
    # --- Melee (spell-combat-rebuild; also usable by NPC combat) ---
    ("Sword_Swing", "Melee", "WmNMgsNMZgMi6DkfCQ6y", "Four different fast sword swings through the air, one at a time with a short silent gap between each, sharp metallic blade swishes, close-mic", 4.0, 0.5, False, "Small", "SFX", 0.75, (0.92, 1.08), "npc", "Sword swing (every attack, on the swing anim notify)"),
    ("Sword_Hit", "Melee", "WDO3DGTWmhbO335o2N7N", "Four separate sword blade hits slicing into a body, one at a time with a short silent gap between each, meaty cut with a heavy thud", 4.0, 0.5, False, "Small", "SFX", 0.85, (0.93, 1.07), "npc", "Sword connects with a character"),
    ("Sword_Clash", "Melee", "B3jdLl68faLEE5ZQxk02", "Three separate clashes of two steel swords, one at a time with a short silent gap between each, bright ringing metal clang", 4.5, 0.5, False, "Small", "SFX", 0.8, (0.93, 1.07), "npc", "Sword blocked / parried by another blade"),
    # --- World (world-jump) ---
    ("WorldJump_Whoosh", "World", "vvM7dhnRArrb8771GmwD", "Deep rushing vortex whoosh, swirling wind and reversed shimmer sweeping past and rising in intensity", 2.5, 0.5, False, None, "SFX", 0.9, None, "world", "World jump departure (JumpSound): play 2D when the jump starts"),
    ("WorldJump_Stinger", "World", "y27bNL9HfqBwRu8XCrMe", "Dramatic magical arrival hit, deep sub boom followed by a bright shimmering ringing tail", 3.0, 0.5, False, None, "SFX", 0.9, None, "world", "World jump arrival in the new world: play 2D on arrival"),
    ("WorldJump_Refused", "World", "LY2cBmAiiKAnj1JiDEVm", "Failed magic attempt, short muted fizzle and sputter ending in a dull low thud", 1.0, 0.5, False, None, "SFX", 0.8, (0.96, 1.04), "world", "World jump refused (RefusedSound): no mirror shard / blocked"),
    ("Coin_Pickup", "World", "yaxdLkrNkrfNQQPJhQYL", "Three separate old metal coins picked up, one at a time with a short silent gap between each, bright clink with a faint magical chime", 3.5, 0.5, False, "Small", "SFX", 0.8, (0.95, 1.08), "world", "Mirror shard (coin) collected (PickupSound)"),
    ("Page_Pickup", "World", "yAuLvKDwpuNFaW1OeAHQ", "Old parchment page picked up and rustled, papery flutter with a soft magical chime", 1.2, 0.5, False, "Small", "SFX", 0.85, (0.97, 1.03), "world", "Book page collected from a tower"),
    ("Door_Unseal", "World", "6lCiJYRyLAG7Ah4ZRCeT", "Ancient magical seal breaking with a resonant chime, then a heavy stone door grinding open", 4.5, 0.5, False, "Medium", "SFX", 0.9, None, "world", "Tower door unsealed / opened"),
    # --- UI ---
    ("UI_Click", "UI", "EG6yg4plgBjoOrnIPll8", "Four separate soft clean interface button clicks, one at a time with silence between each, short subtle ticks", 3.0, 0.6, False, None, "UI", 0.8, (0.97, 1.03), "ui", "Button pressed"),
    ("UI_Hover", "UI", "eefN538HGhdFKQvYNfi6", "Very soft quiet interface hover tick, gentle and airy", 0.5, 0.6, False, None, "UI", 0.5, (0.98, 1.02), "ui", "Button hovered / focus moved"),
    ("UI_Confirm", "UI", "opKkqAygp9JQF1KuxZ5Q", "Pleasant interface confirm sound, short warm two-note chime", 0.8, 0.6, False, None, "UI", 0.8, None, "ui", "Confirm / start game / spell crafted"),
    # --- NPC ---
    ("Infected_Growl", "NPC", "U0HaTdhN1idW1GQYqaUi", "Three different raspy feral human growls, one at a time with a short pause between each, a crazed person snarling through clenched teeth, throaty and wet", 6.0, 0.5, False, "Small", "SFX", 0.85, (0.9, 1.08), "npc", "Infected / Tarnish-touched NPC idle growl, aggro or attack bark"),
    # --- Villain / finale (villain session) ---
    ("Villain_Manifest", "Villain", "Ie8DLENoxEHqaptH1N7K", "Dark ominous supernatural stinger: a reversed rising hiss slamming into a deep sub boom with a dissonant low brass-like cluster and a long dark reverberant tail", 3.0, 0.5, False, "Large", "SFX", 1.0, None, "villain", "The Tarnish's true form appears (dark stinger)"),
    ("Villain_Voice", "Villain", "D60Ok0TTlr1gz78UXx4h", "Three different menacing whispered evil chuckles and hisses, one at a time with a short pause between each, close and breathy", 6.0, 0.5, False, "Medium", "SFX", 1.0, (0.94, 1.04), "villain", "The Tarnish's whispered taunt / laugh; also when he hops hosts"),
    ("Villain_Hop", "Villain", "lc7y2eY6d6hHRVtAmdYf", "Wet dark smoke whoosh with a gloopy squelch, a shadow leaping out of one body and into another", 1.3, 0.5, False, "Medium", "SFX", 1.0, (0.95, 1.05), "villain", "The Tarnish leaves one host for another"),
    ("Villain_Telegraph", "Villain", "bUiK4mC77gh02EFEbkub", "Ominous rising dark energy charge-up building tension for one second and stopping abruptly", 1.0, 0.5, False, "Medium", "SFX", 1.0, (0.98, 1.02), "villain", "1 s charge-up before each of the Tarnish's attacks"),
    ("Villain_Slam", "Villain", "aNfym0Ukyq4oQnqxjSu9", "Massive heavy ground slam shockwave, deep sub impact with rumbling stone debris", 2.0, 0.5, False, "Large", "SFX", 1.0, (0.95, 1.05), "villain", "The Tarnish's heavy attack impact (ground shockwave / tendril strike)"),
    ("Villain_Hurt", "Villain", "LEqFoJwJxUtEl0c7P4tK", "Demonic creature roaring in pain while burning in holy light, sizzling", 1.2, 0.5, False, "Medium", "SFX", 1.0, (0.94, 1.06), "villain", "The Tarnish hit by the Final Spell"),
    ("Villain_Death", "Villain", "i7uetr5kWizIZVG5WEo0", "Dark demonic entity dissolving into ash, an agonized distorted scream fading into whispering wind and crackling embers", 3.6, 0.5, False, "Large", "SFX", 1.0, (0.99, 1.01), "villain", "The Tarnish's death: dissolve and scream"),
    ("FinalSpell_Cast", "Villain", "idFKqFbeRHoUFHiMqlsj", "Huge radiant holy spell blast, bright choir-like swell with shimmering bells and a deep warm boom", 3.2, 0.5, False, "Large", "SFX", 1.0, (0.99, 1.01), "villain", "Hero casts the Final Spell (bright, holy, big)"),
    # --- Spell physics and reactions (procedural, numpy; tools/physics_sfx.py) ---
    ("Fireball_Explode", "Physics", None, "procedural: crack, sub boom, blast sweep, fire roar, stone debris, embers, rumble", 0, 0, False, "Large", "SFX", 1.0, (0.94, 1.06), "spell", "Fireball explosion in the street (spell physics); layer or replace Fire_Impact"),
    ("Water_Shove", "Physics", None, "procedural: rising surge, slap, splash body, bubbles, spray, droplets on stone", 0, 0, False, "Medium", "SFX", 1.0, (0.94, 1.06), "spell", "A wave of water slams into a person (water shove)"),
    ("Shock_Loop", "Physics", None, "procedural: bursts of electric arcs (pulse-modulated noise, distorted hum), crackle bed, sparks", 0, 0, True, "Medium", "SFX", 1.0, None, "npc", "Looping crackle on a shocked target (attach, stop when the shock ends)"),
    ("Shock_Collapse", "Physics", None, "procedural: falling-pitch arc zap, sizzle, body drop", 0, 0, False, "Medium", "SFX", 1.0, (0.95, 1.05), "npc", "Shock ends or kills: final zap and the body dropping"),
    ("Body_Knockback", "Physics", None, "procedural: torso, arm and leg impacts on stone, pebbles, scrape, kit rattle", 0, 0, False, "Small", "SFX", 1.0, (0.93, 1.07), "npc", "A body lands on stone after being thrown (knockback, blast, shove)"),
    ("Burning_Loop", "Physics", None, "procedural: flame roar and breathing, fabric flapping, crackle, low pops", 0, 0, True, "Small", "SFX", 1.0, None, "npc", "Fire on a burning person (attach, stop when the fire goes out)"),
    # --- Giltside squads (procedural, numpy; tools/physics_sfx.py) ---
    ("March_Loop", "Squads", None, "procedural: eight soldiers' boots in step on stone with mail and kit, street reverb", 0, 0, True, "Medium", "SFX", 1.0, None, "squads", "Squad marching in step (loop on the squad centre while it marches)"),
    ("March_Step", "Squads", None, "procedural: one armoured boot step on stone with mail jingle and kit knock", 0, 0, False, "Small", "SFX", 1.0, (0.94, 1.06), "squads", "One soldier's step (footstep notify)"),
    ("Sword_ShieldHit", "Melee", None, "procedural: blade transient and ring, wooden shield thock and crack, steel rim", 0, 0, False, "Small", "SFX", 1.0, (0.93, 1.07), "squads", "A sword strikes a shield"),
    ("Shield_BlockHeavy", "Melee", None, "procedural: weapon strike, wooden shield thud and crack, boss ring, mail rattle", 0, 0, False, "Small", "SFX", 1.0, (0.93, 1.07), "squads", "A shield takes a heavy blow"),
]

M = [
    ("MUS_Gray_Loop", "KuPam18UfFaTIFmlCnLf", "Quiet, melancholic ambient piano piece: soft felt piano, warm sustained strings and a gentle low cello, slow tempo around 70 BPM, introspective rainy-evening mood, sparse and steady with no drums. Keep the energy level constant from start to finish with no big build, no intro and no ending, so it can loop seamlessly.", 155, True, "Music_World", 1.0, "world", "Pewterside (gray, present-day) ambient music loop"),
    ("MUS_Red_Loop", "VSaQka30TWekDBPjDr2a", "Tense medieval war music in a minor key: steady pounding frame drums and deep war drums at a marching 90 BPM, droning low strings, a gritty bowed drone, low horns and a fiddle melody. Urgent and ominous, with consistent energy from start to finish, no intro and no ending, so it can loop seamlessly.", 155, True, "Music_World", 1.0, "world", "Giltside (red, medieval war) music loop"),
    ("MUS_White_Loop", "XskxCkiH48P9J0uwmAtL", "Desolate, eerie dark ambient soundscape: cold breathy synth drones, distant detuned bells, sparse dissonant violin harmonics and a faint low pulse. Very slow, empty and unsettling, no drums. Keep the mood steady from start to finish with no intro and no ending, so it can loop seamlessly.", 155, True, "Music_World", 1.0, "world", "Frostside (white, wasteland) music loop"),
    ("MUS_Combat_Layer", "Qoew9NJzsr5LXwwqe6Pj", "Relentless combat percussion loop: driving large ensemble drums, tight snare rolls, deep booming hits and a low pulsing sub, 100 BPM, aggressive and urgent. Percussion only, no melody, no chords. Constant intensity from start to finish with no intro and no ending, so it can loop seamlessly.", 100, True, "Music_Combat", 0.8, "npc", "Combat layer: fade in over the world loop when enemies engage (push SMX_Jam_Combat)"),
    ("MUS_Victory_Sting", "lTY11DH7YkCWtOAbmDnD", "Short triumphant orchestral victory sting: bold brass fanfare over a timpani roll, resolving on a bright major chord and ending cleanly with a short reverb tail. Starts immediately at full energy.", 7, False, "Music_Combat", 1.0, "npc", "Victory sting: last enemy of an encounter defeated (push SMX_Jam_StingerDuck)"),
]


# Generated as a sequence of separate takes in one clip, sliced into variations on silence.
MULTI = {"Sword_Swing", "Sword_Hit", "Sword_Clash", "UI_Click", "Infected_Growl", "Coin_Pickup", "Villain_Voice"}


def as_dicts():
    sfx = [dict(zip(["name", "folder", "node", "prompt", "gen_s", "influence", "loop", "att", "cls", "vol", "pitch", "owner", "event"], s)) for s in S]
    for d in sfx:
        d["multi"] = d["name"] in MULTI
        # Levels are baked into the waves by level.py (per-sound loudness targets), so every cue plays at 1.0.
        d["vol"] = 1.0
        # Every SFX cue randomizes pitch and volume; loops get a gentler pitch spread.
        if d["pitch"] is None:
            d["pitch"] = (0.98, 1.02) if d["loop"] else (0.97, 1.03)
    mus = [dict(zip(["name", "node", "prompt", "gen_s", "loop", "cls", "vol", "owner", "event"], m)) for m in M]
    for d in mus:
        d["vol"] = 1.0
    return {"sfx": sfx, "music": mus}


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "catalog.json")
    json.dump(as_dicts(), open(out, "w"), indent=1)
    print(out, len(S), len(M))
