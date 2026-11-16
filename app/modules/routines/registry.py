"""Routine definitions. Adding a routine = a module with run(session, ctx) + an entry here.
Definitions live in code (not the DB) so prompts and schedules are versioned and tested."""
from app.config import settings
from app.modules.routines import weekly_plan, weekly_review
from app.modules.routines.service import Routine

ROUTINES: dict[str, Routine] = {
    weekly_review.KEY: Routine(
        key=weekly_review.KEY,
        name="Revisión semanal",
        description="Pregunta la revisión por Telegram, guarda la nota y lanza el plan",
        cron="0 18 * * sun",  # same time as the "Revisión semanal" event in Calendar
        timezone=settings.TIMEZONE,
        engine="litellm",
        run=weekly_review.run,
        catch_up_hours=15,  # Sunday 18:00 missed → still asks until Monday 09:00
    ),
    weekly_plan.KEY: Routine(
        key=weekly_plan.KEY,
        name="Planificación semanal",
        description="Propone la semana en bloques respetando el calendario; aprobación por Telegram",
        cron=None,  # launched after the review (or skip), or /plan
        timezone=settings.TIMEZONE,
        engine="litellm",
        run=weekly_plan.run,
    ),
}


def get_routine(key: str) -> Routine | None:
    return ROUTINES.get(key)
