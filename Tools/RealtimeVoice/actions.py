"""The whitelist of things an NPC may do because of what the player said.

Two checks guard every action. The relay offers the reply model only actions that are (1) on this list, (2) allowed
for this kind of NPC and (3) reported possible right now by the game (`actions` in the NPC facts, which the game's
executor computes: target exists, cooldown over, ...). It accepts the model's choice only if it is one of those
offers. The game then checks again when it performs it (UReflectionsNpcActionExecutor). No free-form actions.
"""

import re

ALL_KINDS = frozenset(("civilian", "guard", "soldier", "tarnished", "tarnish"))
PEOPLE = frozenset(("civilian", "guard", "soldier"))

# Quest verbs from the quest system (UReflectionsQuestSubsystem::GetQuestActions). Their targets are quest ids (and
# "quest.choice" for choose), so they are not a fixed list: the game names the exact ones possible right now, the relay
# checks their shape, and the model may only pick one of those exact offers. The quest system re-checks on execution.
QUEST_VERBS = {
    "offer_quest": "offer the player quest '{target}' (only when they ask for work or help, or clearly want it)",
    "accept": "the player takes on quest '{target}' (only after a clear yes)",
    "decline": "the player turns down quest '{target}' (after a clear no)",
    "turn_in": "take the player's finished work for quest '{target}' and thank them",
    "give_hint": "give a hint for quest '{target}' (when they ask for help with it)",
    "choose": "the player makes the choice '{target}' (only when they clearly state it)",
    "talk": "this conversation counts for quest '{target}'",
    "deliver": "receive the player's delivery for quest '{target}'",
}
QUEST_TARGET = re.compile(r"[A-Za-z0-9_.-]{1,64}")

ACTIONS = {
    "point_the_way": {
        "kinds": frozenset(("civilian", "guard", "soldier")),
        "targets": ("nearest_mirror_page", "nearest_shard", "gilt_tower"),
        "describe": "turn and point the player toward {target}",
    },
    "share_lore": {
        "kinds": ALL_KINDS,
        "targets": ("sides", "tarnish", "shards", "pages", "final_spell", "gilt_tower"),
        "describe": "tell the player what you know about {target}",
    },
    "warn_guards": {
        "kinds": frozenset(("civilian",)),
        "targets": ("none",),
        "describe": "shout for the city watch (only if the player asks for help or you are in danger)",
    },
    "end_conversation": {
        "kinds": ALL_KINDS,
        "targets": ("none",),
        "describe": "end the conversation and turn away (if the player is rude, says goodbye, or you must go)",
    },
}


def parse_offer(text):
    """'point_the_way:nearest_mirror_page' -> ('point_the_way', 'nearest_mirror_page'); 'warn_guards' -> (.., 'none')."""
    if not isinstance(text, str):
        return None
    name, _, target = text.partition(":")
    target = target or "none"
    if name in QUEST_VERBS:
        return (name, target) if QUEST_TARGET.fullmatch(target) else None
    spec = ACTIONS.get(name)
    if spec is None or target not in spec["targets"]:
        return None
    return name, target


def offers_for(persona_group, reported):
    """The (name, target) pairs the model may choose: possible in the game AND allowed for this kind of NPC."""
    offers = []
    for item in reported if isinstance(reported, (list, tuple)) else []:
        parsed = parse_offer(item)
        kinds = PEOPLE if parsed and parsed[0] in QUEST_VERBS else (ACTIONS[parsed[0]]["kinds"] if parsed else ())
        if parsed and persona_group in kinds and parsed not in offers:
            offers.append(parsed)
        if len(offers) >= 24:
            break
    return offers


def describe(offers):
    def means(name, target):
        if name in QUEST_VERBS:
            return QUEST_VERBS[name].format(target=target)
        return ACTIONS[name]["describe"].format(target=target.replace("_", " "))
    return [{"action": name, "target": target, "means": means(name, target)} for name, target in offers]


def validate(choice_name, choice_target, offers):
    """The model's choice, if it is exactly one of the offers; else None."""
    pair = (choice_name, choice_target or "none")
    return pair if pair in offers else None
