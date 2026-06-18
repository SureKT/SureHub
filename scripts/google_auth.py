"""OAuth one-time para Google Calendar. Corre UNA vez en local (abre navegador):
    python scripts/google_auth.py
Requiere GOOGLE_CALENDAR_CREDENTIALS (client secret de un OAuth Client tipo Desktop,
Calendar API habilitada). Guarda el token en GOOGLE_CALENDAR_TOKEN.
En prod: copia el token generado al volumen /srv/surehub/data del contenedor bot."""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings
from app.services.calendar import SCOPES


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(
        settings.GOOGLE_CALENDAR_CREDENTIALS, SCOPES
    )
    creds = flow.run_local_server(port=0)
    Path(settings.GOOGLE_CALENDAR_TOKEN).write_text(creds.to_json(), encoding="utf-8")
    print(f"Token guardado en {settings.GOOGLE_CALENDAR_TOKEN}")


if __name__ == "__main__":
    main()
