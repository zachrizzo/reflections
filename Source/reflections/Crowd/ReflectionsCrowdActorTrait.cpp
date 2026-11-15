#include "Crowd/ReflectionsCrowdActorTrait.h"
#include "MassActorSubsystem.h"
#include "MassEntityTemplateRegistry.h"
void UReflectionsCrowdActorTrait::BuildTemplate(FMassEntityTemplateBuildContext& BuildContext, const UWorld& World) const
{
    BuildContext.AddFragment<FMassActorFragment>();
}
