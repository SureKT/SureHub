"""Routine definitions. Adding a routine = a module with run(session, ctx) + an entry here.
Definitions live in code (not the DB) so prompts and schedules are versioned and tested."""
from app.config import settings
from app.modules.routines import weekly_plan
from app.modules.routines.service import Routine

ROUTINES: dict[str, Routine] = {
    weekly_plan.KEY: Routine(
        key=weekly_plan.KEY,
        name="Planificación semanal",
        description="Propone la semana en bloques respetando el calendario; aprobación por Telegram",
        cron="0 19 * * sun",
        timezone=settings.TIMEZONE,
        engine="litellm",
        run=weekly_plan.run,
        catch_up_hours=14,  # Sunday 19:00 missed → still runs until Monday 09:00
    ),
}


def get_routine(key: str) -> Routine | None:
    return ROUTINES.get(key)
