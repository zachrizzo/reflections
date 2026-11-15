// Built-in quests: the main story expressed over the existing progression (shards, stepping through, the three
// mirror pages, the towers, the Final Spell, the finale), plus one test side quest that exercises every part of the
// system. Story packs (/Game/Quests/DA_QuestPack_Story) replace these by id; a story main quest replaces "main".

#include "Quests/ReflectionsQuestTypes.h"

#define LOCTEXT_NAMESPACE "ReflectionsQuestBuiltins"

namespace ReflectionsQuestBuiltins
{
    static FReflectionsQuestObjective Objective(FName Id, EReflectionsObjectiveType Type, const FText& Text, FName Target, int32 Count = 1)
    {
        FReflectionsQuestObjective O;
        O.Id = Id;
        O.Type = Type;
        O.Text = Text;
        O.Target = Target;
        O.Count = Count;
        return O;
    }

    static FReflectionsQuestDef MainQuest()
    {
        FReflectionsQuestDef Q;
        Q.Id = TEXT("main");
        Q.bMain = true;
        Q.bAutoStart = true;
        Q.bTurnIn = false;
        Q.SortOrder = 0;
        Q.Title = LOCTEXT("MainTitle", "The Silvered City");
        Q.Summary = LOCTEXT("MainSummary", "Lanthorne is one city in three reflections, and the Tarnish is spreading through all of them. Mend the mirror before it takes the town.");

        {
            FReflectionsQuestStep S;
            S.Id = TEXT("shard");
            S.Title = LOCTEXT("MainShardTitle", "A Shard of Glass");
            S.Description = LOCTEXT("MainShardDesc", "Mirror shards are the only way between the sides. The tarnished carry them, and so does the street, if you look.");
            FReflectionsQuestObjective O = Objective(TEXT("shard"), EReflectionsObjectiveType::Event, LOCTEXT("MainShardObj", "Find a mirror shard"), TEXT("ShardCollected"));
            O.Hints = {LOCTEXT("MainShardHint1", "Shards glint on the ground where the Tarnish has been."), LOCTEXT("MainShardHint2", "Beat a tarnished townsperson and they drop a shard of their side.")};
            S.Objectives.Add(O);
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("step");
            S.Title = LOCTEXT("MainStepTitle", "Through the Glass");
            S.Description = LOCTEXT("MainStepDesc", "A shard and most of your magic will carry you to the same spot on another side of Lanthorne. Find high ground first: you arrive where you stand.");
            FReflectionsQuestObjective O = Objective(TEXT("jump"), EReflectionsObjectiveType::WorldJump, LOCTEXT("MainStepObj", "Step through to another side"), NAME_None);
            O.Hints = {LOCTEXT("MainStepHint1", "Hold X (keyboard) or Y (gamepad) to rise a side; hold Z or R3 to sink one."), LOCTEXT("MainStepHint2", "A jump costs a shard of the side you go to and most of your mana.")};
            S.Objectives.Add(O);
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("pages");
            S.Title = LOCTEXT("MainPagesTitle", "Three Towers, Three Pages");
            S.Description = LOCTEXT("MainPagesDesc", "Each side keeps one page of the mirror at the top of its tower. Pewterside's stair is open. The Gilt Tower is sealed, and Frostside's can only be reached from inside Giltside's.");
            FReflectionsQuestObjective Gray = Objective(TEXT("page_gray"), EReflectionsObjectiveType::Event, LOCTEXT("MainPageGray", "Pewterside's page"), TEXT("PageFound"));
            Gray.Spell = TEXT("Pewterside");
            Gray.Marker = TEXT("Tower_Pewterside");
            Gray.Hints = {LOCTEXT("MainPageGrayHint", "Pewterside's tower stair climbs all the way up. The page waits at the top.")};
            FReflectionsQuestObjective Key = Objective(TEXT("key"), EReflectionsObjectiveType::Event, LOCTEXT("MainKey", "Find the key to the Gilt Tower"), TEXT("KeyFound"));
            Key.Spell = TEXT("GiltTowerKey");
            Key.bOptional = true;
            Key.Hints = {LOCTEXT("MainKeyHint", "The Gilt Tower's key is somewhere else in Giltside.")};
            FReflectionsQuestObjective Red = Objective(TEXT("page_red"), EReflectionsObjectiveType::Event, LOCTEXT("MainPageRed", "Giltside's page"), TEXT("PageFound"));
            Red.Spell = TEXT("Giltside");
            Red.Marker = TEXT("Tower_Giltside");
            Red.Hints = {LOCTEXT("MainPageRedHint", "Unseal the Gilt Tower with its key and climb.")};
            FReflectionsQuestObjective White = Objective(TEXT("page_white"), EReflectionsObjectiveType::Event, LOCTEXT("MainPageWhite", "Frostside's page"), TEXT("PageFound"));
            White.Spell = TEXT("Frostside");
            White.Marker = TEXT("Tower_Frostside");
            White.Hints = {LOCTEXT("MainPageWhiteHint", "Frostside's tower is locked from the ground. Stand inside the Gilt Tower and rise.")};
            S.Objectives = {Gray, Key, Red, White};
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("finale");
            S.Title = LOCTEXT("MainFinaleTitle", "The Mirror Made Whole");
            S.Description = LOCTEXT("MainFinaleDesc", "With all three pages the mirror remembers the Final Spell. The Tarnish knows it too, and waits at the top of Frostside's tower.");
            FReflectionsQuestObjective Arena = Objective(TEXT("arena"), EReflectionsObjectiveType::GoTo, LOCTEXT("MainArenaObj", "Face the Tarnish atop Frostside's tower"), TEXT("VillainArena"));
            Arena.Hints = {LOCTEXT("MainArenaHint", "Climb Frostside's tower: through the Gilt Tower, then rise.")};
            S.Objectives.Add(Arena);
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("boss");
            S.Title = LOCTEXT("MainBossTitle", "Break the Tarnish");
            S.Description = LOCTEXT("MainBossDesc", "Ordinary spells barely mark it. Only the Final Spell (F, or X / Square on a gamepad) cuts through.");
            FReflectionsQuestObjective Boss = Objective(TEXT("boss"), EReflectionsObjectiveType::Event, LOCTEXT("MainBossObj", "Defeat the Tarnish with the Final Spell"), TEXT("BossDefeated"));
            Boss.Marker = TEXT("VillainArena");
            Boss.Hints = {LOCTEXT("MainBossHint", "Press F (X / Square on a gamepad) to cast the Final Spell. Keep moving between casts.")};
            S.Objectives.Add(Boss);
            Q.Steps.Add(S);
        }
        return Q;
    }

    /** Test side quest: give, track, collect, spell hit, deliver, choice, turn in, reward. */
    static FReflectionsQuestDef TestQuest()
    {
        FReflectionsQuestDef Q;
        Q.Id = TEXT("test_ledger");
        Q.bTest = true;
        Q.Giver = TEXT("QuestTester");
        Q.Side = EReflectionsQuestSide::Giltside;
        Q.SortOrder = 900;
        Q.Title = LOCTEXT("TestTitle", "The Clerk's Lost Ledger");
        Q.Summary = LOCTEXT("TestSummary", "A clerk lost her ledger near a cold brazier. Find it, relight the brazier so she can read it, and bring it back.");
        const FName Ada(TEXT("QuestTester"));
        Q.OfferLines = {ReflectionsQuest::Line(Ada, LOCTEXT("TestOffer1", "You there, with the coat. I dropped my ledger by the old brazier and the fog ate it.")),
                        ReflectionsQuest::Line(Ada, LOCTEXT("TestOffer2", "Find it for me? And light that brazier, I can't read a word in this murk."))};
        Q.AcceptLines = {ReflectionsQuest::Line(Ada, LOCTEXT("TestAccept", "Bless you. It's bound in red, you can't miss it."))};
        Q.DeclineLines = {ReflectionsQuest::Line(Ada, LOCTEXT("TestDecline", "Oh. Well. It'll be here when you change your mind."))};
        Q.ReminderLines = {ReflectionsQuest::Line(Ada, LOCTEXT("TestReminder", "Any luck with my ledger?"))};
        Q.TurnInLines = {ReflectionsQuest::Line(Ada, LOCTEXT("TestTurnIn", "My ledger! Every coin accounted for. Take these for your trouble."))};
        Q.Reward.Coins = 2;
        Q.Reward.Mana = 25.0f;
        Q.Reward.Reputation.Add({TEXT("QuestTester"), 15.0f});
        Q.Reward.Unlocks.Add(TEXT("Test_LedgerReturned"));
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("find");
            S.Title = LOCTEXT("TestFindTitle", "In the Fog");
            S.Description = LOCTEXT("TestFindDesc", "The clerk's ledger lies somewhere near the old brazier.");
            FReflectionsQuestObjective Find = Objective(TEXT("ledger"), EReflectionsObjectiveType::Collect, LOCTEXT("TestFindObj", "Find the red ledger"), TEXT("TestLedger"));
            Find.Marker = TEXT("Item_TestLedger");
            Find.Hints = {LOCTEXT("TestFindHint", "Follow the marker; the ledger glows faintly.")};
            S.Objectives.Add(Find);
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("light");
            S.Title = LOCTEXT("TestLightTitle", "A Little Light");
            S.Description = LOCTEXT("TestLightDesc", "The brazier is cold. A fire spell should wake it.");
            FReflectionsQuestObjective Hit = Objective(TEXT("brazier"), EReflectionsObjectiveType::SpellHit, LOCTEXT("TestLightObj", "Light the brazier with fire"), TEXT("Spot_TestBrazier"));
            Hit.Spell = TEXT("Fire");
            Hit.Radius = 350.0f;
            Hit.Hints = {LOCTEXT("TestLightHint", "Any fire spell will do. Aim at the marker.")};
            S.Objectives.Add(Hit);
            Q.Steps.Add(S);
        }
        {
            FReflectionsQuestStep S;
            S.Id = TEXT("return");
            S.Title = LOCTEXT("TestReturnTitle", "Back to the Clerk");
            S.Description = LOCTEXT("TestReturnDesc", "The ledger is readable now. Something in it does not add up.");
            FReflectionsQuestObjective Give = Objective(TEXT("deliver"), EReflectionsObjectiveType::Deliver, LOCTEXT("TestReturnObj", "Bring the ledger to the clerk"), TEXT("QuestTester"));
            Give.Item = TEXT("TestLedger");
            Give.CompleteLines = {ReflectionsQuest::Line(TEXT("QuestTester"), LOCTEXT("TestReturnLine", "You read it, didn't you. Then you saw the missing page. Will you keep that to yourself?"))};
            S.Objectives.Add(Give);
            S.Speaker = TEXT("QuestTester");
            FReflectionsQuestChoice Keep;
            Keep.Id = TEXT("keep_secret");
            Keep.Text = LOCTEXT("TestChoiceKeep", "Your secret is safe.");
            Keep.Response = LOCTEXT("TestChoiceKeepReply", "Thank you. I won't forget it.");
            Keep.Journal = LOCTEXT("TestChoiceKeepLog", "I promised to keep the clerk's missing page quiet.");
            Keep.Reward.Reputation.Add({TEXT("QuestTester"), 10.0f});
            FReflectionsQuestChoice Tell;
            Tell.Id = TEXT("tell_guard");
            Tell.Text = LOCTEXT("TestChoiceTell", "The guards should know.");
            Tell.Response = LOCTEXT("TestChoiceTellReply", "...Fine. Do what you think is right.");
            Tell.Journal = LOCTEXT("TestChoiceTellLog", "I told the clerk the guards should hear about the missing page.");
            Tell.Reward.Reputation.Add({TEXT("QuestTester"), -10.0f});
            S.Choices = {Keep, Tell};
            S.ChoicePerson = TEXT("QuestTester");
            Q.Steps.Add(S);
        }
        return Q;
    }

    void Build(TArray<FReflectionsQuestDef>& OutQuests, TArray<FReflectionsQuestPerson>& OutPeople)
    {
        OutQuests.Add(MainQuest());
        OutQuests.Add(TestQuest());

        FReflectionsQuestPerson Tester;
        Tester.Id = TEXT("QuestTester");
        Tester.DisplayName = LOCTEXT("TesterName", "Ada Pell");
        Tester.Title = LOCTEXT("TesterTitle", "Ledger clerk");
        Tester.Side = EReflectionsQuestSide::Giltside;
        Tester.Archetype = TEXT("Civilian");
        Tester.Sex = TEXT("F");
        Tester.IdleLines = {LOCTEXT("TesterIdle", "Careful in the fog. It hides more than ledgers.")};
        OutPeople.Add(Tester);
    }
}

#undef LOCTEXT_NAMESPACE
