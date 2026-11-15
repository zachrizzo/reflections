#pragma once
#include "CoreMinimal.h"

class UPackage
{
public:
    explicit UPackage(FString InName) : Name(std::move(InName)) {}
    FString GetName() const { return Name; }
private:
    FString Name;
};
