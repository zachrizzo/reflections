#include "SpellCrafting/ReflectionsSpellRecipeRelay.h"

#include "SpellCrafting/ReflectionsSpellCraftingLibrary.h"

#include "Dom/JsonObject.h"
#include "HAL/PlatformMisc.h"
#include "IWebSocket.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Policies/CondensedJsonPrintPolicy.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "WebSocketsModule.h"

namespace
{
    const TCHAR* TokenVariable = TEXT("REFLECTIONS_SPELL_LOCAL_TOKEN");
    const TCHAR* RelayUrl = TEXT("ws://127.0.0.1:8766");

#if !UE_BUILD_SHIPPING
    /**
     * The relay's per-launch token: from the environment when Start-SpellRelay.ps1 launched this editor, otherwise
     * from the git-ignored file a relay started on its own publishes (and deletes on exit). Never a key.
     */
    FString LocalToken()
    {
        const FString FromEnvironment = FPlatformMisc::GetEnvironmentVariable(TokenVariable);
        if (FromEnvironment.Len() >= 32) return FromEnvironment;
        FString FromFile;
        if (FFileHelper::LoadFileToString(FromFile, *FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("SpellCrafting"), TEXT("relay-token"))))
        {
            FromFile.TrimStartAndEndInline();
            if (FromFile.Len() >= 32 && FromFile.Len() <= 128) return FromFile;
        }
        return FString();
    }
#endif
}

bool UReflectionsSpellRecipeRelay::IsConfigured()
{
#if UE_BUILD_SHIPPING
    return false;
#else
    return LocalToken().Len() >= 32;
#endif
}

void UReflectionsSpellRecipeRelay::Finish(bool bOk, const FCraftedSpellRecipe& Recipe, const FString& Message)
{
    FDone Done = MoveTemp(Pending);
    Pending = nullptr;
    if (Socket.IsValid())
    {
        Socket->OnConnected().Clear();
        Socket->OnConnectionError().Clear();
        Socket->OnMessage().Clear();
        Socket->OnClosed().Clear();
        if (Socket->IsConnected()) Socket->Close();
        Socket.Reset();
    }
    if (Done) Done(bOk, Recipe, Message);
}

void UReflectionsSpellRecipeRelay::Request(const FString& Text, FDone Done)
{
#if UE_BUILD_SHIPPING
    Done(false, FCraftedSpellRecipe(), TEXT("The relay is not available in this build."));
#else
    if (Pending)
    {
        Done(false, FCraftedSpellRecipe(), TEXT("A description is already being interpreted."));
        return;
    }
    const FString Token = LocalToken();
    if (Token.Len() < 32)
    {
        Done(false, FCraftedSpellRecipe(), TEXT("The spell relay is not running."));
        return;
    }
    Pending = MoveTemp(Done);
    StartedAt = FPlatformTime::Seconds();
    if (!FModuleManager::Get().IsModuleLoaded(TEXT("WebSockets"))) FModuleManager::Get().LoadModule(TEXT("WebSockets"));
    Socket = FWebSocketsModule::Get().CreateWebSocket(RelayUrl);
    const FString Sentence = Text.Left(400);
    TWeakObjectPtr<UReflectionsSpellRecipeRelay> Weak(this);
    Socket->OnConnected().AddLambda([Weak, Token, Sentence]()
    {
        if (!Weak.IsValid() || !Weak->Socket.IsValid()) return;
        TSharedRef<FJsonObject> Message = MakeShared<FJsonObject>();
        Message->SetStringField(TEXT("type"), TEXT("describe"));
        Message->SetStringField(TEXT("token"), Token);
        Message->SetStringField(TEXT("text"), Sentence);
        FString Out;
        const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&Out);
        FJsonSerializer::Serialize(Message, Writer);
        Weak->Socket->Send(Out);
    });
    Socket->OnConnectionError().AddLambda([Weak](const FString&)
    {
        if (Weak.IsValid()) Weak->Finish(false, FCraftedSpellRecipe(), TEXT("The spell relay is not running."));
    });
    Socket->OnMessage().AddLambda([Weak](const FString& Raw)
    {
        if (!Weak.IsValid()) return;
        TSharedPtr<FJsonObject> Object;
        if (!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Raw), Object) || !Object.IsValid())
        {
            Weak->Finish(false, FCraftedSpellRecipe(), TEXT("The relay sent something unreadable."));
            return;
        }
        FString Type;
        Object->TryGetStringField(TEXT("type"), Type);
        if (Type == TEXT("recipe"))
        {
            const TSharedPtr<FJsonObject>* RecipeObject = nullptr;
            FCraftedSpellRecipe Recipe;
            FString RecipeJson;
            if (Object->TryGetObjectField(TEXT("recipe"), RecipeObject) && RecipeObject)
            {
                const TSharedRef<TJsonWriter<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>> Writer = TJsonWriterFactory<TCHAR, TCondensedJsonPrintPolicy<TCHAR>>::Create(&RecipeJson);
                FJsonSerializer::Serialize(RecipeObject->ToSharedRef(), Writer);
            }
            if (!RecipeJson.IsEmpty() && UReflectionsSpellCraftingLibrary::FromJson(RecipeJson, Recipe))
            {
                Weak->Finish(true, Recipe, TEXT("Interpreted by the dev relay."));
                return;
            }
            Weak->Finish(false, FCraftedSpellRecipe(), TEXT("The relay's recipe did not fit the grammar."));
            return;
        }
        FString Error = TEXT("The relay could not interpret that.");
        Object->TryGetStringField(TEXT("message"), Error);
        Weak->Finish(false, FCraftedSpellRecipe(), Error.Left(160));
    });
    Socket->OnClosed().AddLambda([Weak](int32, const FString&, bool)
    {
        if (Weak.IsValid() && Weak->Pending) Weak->Finish(false, FCraftedSpellRecipe(), TEXT("The spell relay closed the connection."));
    });
    Socket->Connect();
#endif
}

void UReflectionsSpellRecipeRelay::BeginDestroy()
{
    Pending = nullptr;
    if (Socket.IsValid())
    {
        Socket->OnConnected().Clear();
        Socket->OnConnectionError().Clear();
        Socket->OnMessage().Clear();
        Socket->OnClosed().Clear();
        if (Socket->IsConnected()) Socket->Close();
        Socket.Reset();
    }
    Super::BeginDestroy();
}
