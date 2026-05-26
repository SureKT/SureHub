"""
Analyzes a Spotify library using Claude (reuses app.services.llm).
"""
import json
from collections import defaultdict

from app.services.llm import client as llm_client


# ── Stats ─────────────────────────────────────────────────────────────────────

def compute_stats(liked_tracks: list, playlists: list) -> dict:
    all_playlist_ids: set = set()
    for p in playlists:
        all_playlist_ids.update(p.get("track_ids", []))

    genre_counts: dict = defaultdict(int)
    for t in liked_tracks:
        for g in t.get("genres", []):
            genre_counts[g] += 1

    top_genres = sorted(genre_counts.items(), key=lambda x: -x[1])[:30]
    unorganized = [t for t in liked_tracks if t["id"] not in all_playlist_ids]

    def avg(field: str) -> float | None:
        vals = [t[field] for t in liked_tracks if t.get(field) is not None]
        return round(sum(vals) / len(vals), 3) if vals else None

    return {
        "total_liked": len(liked_tracks),
        "total_playlists": len(playlists),
        "unorganized_count": len(unorganized),
        "unorganized_ids": [t["id"] for t in unorganized],
        "top_genres": top_genres,
        "avg_energy": avg("energy"),
        "avg_valence": avg("valence"),
        "avg_danceability": avg("danceability"),
        "avg_tempo": avg("tempo"),
    }


# ── Claude prompt ─────────────────────────────────────────────────────────────

def _build_prompt(liked_tracks: list, playlists: list, stats: dict) -> str:
    all_playlist_ids: set = set()
    for p in playlists:
        all_playlist_ids.update(p.get("track_ids", []))

    unorganized = [t for t in liked_tracks if t["id"] not in all_playlist_ids]
    sample = [t for t in unorganized if t.get("energy") is not None][:80]

    playlist_info = "\n".join(
        f"  - '{p['name']}' ({len(p.get('track_ids', []))} tracks)"
        + (f": {p['description']}" if p.get("description") else "")
        for p in playlists
    )

    track_lines = "\n".join(
        f"  {t['name']} – {t['artist']} | "
        f"genres: {', '.join(t['genres'][:3]) or 'unknown'} | "
        f"energy:{t['energy']:.2f} valence:{t['valence']:.2f} "
        f"dance:{t['danceability']:.2f} BPM:{int(t.get('tempo') or 0)}"
        for t in sample
    )

    return f"""Eres un experto en música analizando la biblioteca de Spotify del usuario.

ESTADÍSTICAS DE LA BIBLIOTECA:
- Liked songs totales: {stats['total_liked']}
- Playlists existentes: {stats['total_playlists']}
- Canciones sin organizar: {stats['unorganized_count']}
- Energía promedio: {stats['avg_energy']} | Positividad: {stats['avg_valence']} | Bailabilidad: {stats['avg_danceability']}
- Tempo promedio: {stats['avg_tempo']} BPM

TOP GÉNEROS EN LIKED SONGS:
{json.dumps(dict(stats['top_genres'][:20]), ensure_ascii=False, indent=2)}

PLAYLISTS ACTUALES:
{playlist_info if playlist_info else '  (ninguna)'}

MUESTRA DE CANCIONES SIN ORGANIZAR ({len(sample)} de {stats['unorganized_count']}):
{track_lines if track_lines else '  (todas organizadas)'}

Analiza esta biblioteca y responde con:

1. **DIAGNÓSTICO**: Estado actual y patrones detectados en la biblioteca.

2. **PLAYLISTS NUEVAS SUGERIDAS**: Para cada una: nombre, descripción y criterio de selección \
(géneros y/o audio features como energía, tempo, bailabilidad).

3. **REORGANIZACIÓN**: Canciones mal ubicadas, playlists solapadas o candidatas a fusión.

4. **RECOMENDACIONES DE DESCUBRIMIENTO**: Géneros o artistas similares que enriquecerían la biblioteca.

Responde en español, con estructura clara y accionable."""


# ── Main entry ────────────────────────────────────────────────────────────────

def analyze_library(liked_tracks: list, playlists: list) -> tuple[dict, str]:
    """Returns (stats, analysis_text)."""
    stats = compute_stats(liked_tracks, playlists)
    prompt = _build_prompt(liked_tracks, playlists, stats)

    response = llm_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    return stats, response.content[0].text
