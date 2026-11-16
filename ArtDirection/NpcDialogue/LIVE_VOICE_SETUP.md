# Live NPC voice: player setup (packaged Windows build)

Without a key the game still works: NPCs answer with their recorded lines, and the talk prompt says "Add your Gemini
API key in Settings to talk with characters in real time." Live talk needs your own Google Gemini API key and
microphone access.

1. **Unzip the whole game** to a normal folder (for example `C:\Games\Reflections`). Don't run it from inside the zip or
   from Program Files: the game saves your key next to its voice helper.
2. **Get a key** at Google AI Studio. Restrict it to the Generative Language API and set a low quota: you pay for its use.
3. **Add it in the game:** Settings → "Gemini API key". Click the box, paste your key, press **Save**. The status turns
   to "Saved" and live talk starts; you don't need to restart. To remove the key, clear the box and press Save.
   (Advanced: the game stores it as `Windows\reflections\Content\NpcDialogue\Relay\keys.json`, in the format of
   `keys.json.example` in that folder. Don't share that file.)
4. **Allow the microphone:** go to Windows Settings → Privacy & security → Microphone. Turn on "Microphone access" and
   "Let desktop apps access your microphone". Set the microphone you use as the **default input device**
   (Settings → System → Sound → Input).
5. If Windows SmartScreen or your antivirus asks about `NpcDialogueRelay.exe`, allow it. It is the game's local voice
   helper and talks only to Google's Gemini service.
6. **Talk:** walk up to someone and **hold E** (gamepad: D-pad Down). You'll see "Listening... say anything". Speak, then
   let go. People with quest business show "E Talk to <name>" and open the quest dialogue instead. **Enter** lets you type.

## If it still doesn't hear you

Open `Windows\reflections\Saved\Logs\reflections.log` and search for `NpcDialogue`:

| Log line | Meaning |
|---|---|
| `No NPC dialogue helper at ...` | The `Relay` folder is missing from this build: no live voice possible. |
| `No keys.json for the NPC dialogue helper` | No key saved yet (step 3). |
| `NPC dialogue key saved.` | Settings saved a key (the key itself is never logged). |
| `The NPC dialogue helper exited (code 2)` | The saved key file is unreadable. Save the key again in Settings. |
| `NPC dialogue helper listening on port 8765.` | The helper runs. If the NPC still answers with recorded lines, check the microphone (step 4), the key's quota, and the helper's own log, `Windows\reflections\Saved\NpcDialogue\relay.log`. |
