# NPC conversation in Reflections

The player can walk up to a dialogue-enabled NPC and hold **E** or **D-pad Down** to speak. Release the key to send the turn. The **T** key also works. Press **Enter** to type when the local dialogue relay is available. The conversation overlay displays the reply and the speaking NPC faces the player when its movement allows it.

The NPC system selects an existing voice from the baked roster. Recorded cues and voice lines remain under `Content/Audio/Jam/Voice`. The dialogue component can play a matching baked reply when the relay is unavailable. The live relay uses the same voice roster, speech recognition, reply generation, synthesis, and cached replies.

For editor setup, see [the dialogue relay README](../../Tools/RealtimeVoice/README.md). The relay reads credentials locally. Keep generated reply caches and credentials in their local locations.

Test Town has a registered conversation NPC by the market stalls. Use it to check baked replies or the local relay. The offline relay tests run independently of Unreal.
