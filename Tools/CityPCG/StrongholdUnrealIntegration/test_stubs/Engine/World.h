#pragma once
#include "CoreMinimal.h"
#include "UObject/Package.h"

enum ENetMode { NM_Standalone, NM_DedicatedServer, NM_ListenServer, NM_Client };

class UWorld
{
public:
    UWorld(ENetMode InMode, FString InName, bool InGameWorld = true)
        : Mode(InMode), Package(std::move(InName)), GameWorld(InGameWorld) {}
    ENetMode GetNetMode() const { return Mode; }
    bool IsGameWorld() const { return GameWorld; }
    UPackage* GetOutermost() { return &Package; }
    static FString RemovePIEPrefix(FString Name)
    {
        const std::size_t Slash = Name.Value.find_last_of('/');
        const std::size_t Start = Slash == std::string::npos ? 0 : Slash + 1;
        if (Name.Value.compare(Start, 7, "UEDPIE_") != 0) return Name;
        std::size_t Index = Start + 7;
        while (Index < Name.Value.size() && std::isdigit(static_cast<unsigned char>(Name.Value[Index]))) ++Index;
        if (Index < Name.Value.size() && Name.Value[Index] == '_') Name.Value.erase(Start, Index - Start + 1);
        return Name;
    }
private:
    ENetMode Mode;
    UPackage Package;
    bool GameWorld;
};
