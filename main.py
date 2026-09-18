import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


app = FastAPI(title="Multi-Sport Prediction App")


# ============================================================
# OPENFOOTBALL
# ============================================================

OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/"
    "openfootball/football.json/master/"
)


def get_openfootball_league(
    season: str = "2026-27",
    league_file: str = "en.1.json",
):
    """
    Récupère les données d'une compétition depuis OpenFootball.
    Exemple :
    2026-27/en.1.json = Premier League anglaise
    """

    url = f"{OPENFOOTBALL_BASE}{season}/{league_file}"

    try:
        with urlopen(url, timeout=15) as response:
            data = json.loads(
                response.read().decode("utf-8")
            )

        return data

    except HTTPError as error:
        return {
            "error": "OpenFootball HTTP error",
            "status": error.code,
            "url": url,
        }

    except URLError as error:
        return {
            "error": "Impossible de contacter OpenFootball",
            "details": str(error.reason),
            "url": url,
        }

    except Exception as error:
        return {
            "error": "Erreur lors de la lecture des données",
            "details": str(error),
            "url": url,
        }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "multi-sport-prediction-app",
        "data_source": "OpenFootball",
    }


# ============================================================
# TEST OPENFOOTBALL
# ============================================================

@app.get("/api/football/test")
def football_test():

    data = get_openfootball_league()

    if "error" in data:
        return data

    matches = data.get("matches", [])

    return {
        "status": "ok",
        "source": "OpenFootball",
        "competition": data.get("name"),
        "number_of_matches": len(matches),
        "sample_matches": matches[:5],
    }


# ============================================================
# TOUS LES MATCHS
# ============================================================

@app.get("/api/football/matches")
def football_matches():

    data = get_openfootball_league()

    if "error" in data:
        return data

    return {
        "status": "ok",
        "source": "OpenFootball",
        "competition": data.get("name"),
        "matches": data.get("matches", []),
    }


# ============================================================
# PAGE PRINCIPALE
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home():

    return """
    <!DOCTYPE html>

    <html lang="fr">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>Multi-Sport Prediction App</title>

        <style>

            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #0f172a;
                color: white;
            }

            .container {
                max-width: 900px;
                margin: auto;
                padding: 30px 20px;
            }

            h1 {
                font-size: 32px;
                margin-bottom: 10px;
            }

            .card {
                background: #1e293b;
                border-radius: 16px;
                padding: 24px;
                margin-top: 20px;
            }

            .sport {
                display: inline-block;
                padding: 10px 16px;
                margin: 5px;
                border-radius: 10px;
                background: #334155;
            }

            .status {
                margin-top: 25px;
                padding: 15px;
                background: #334155;
                border-radius: 10px;
            }

            a {
                color: #38bdf8;
                text-decoration: none;
            }

            a:hover {
                text-decoration: underline;
            }

        </style>

    </head>

    <body>

        <div class="container">

            <h1>
                🏆 Multi-Sport Prediction App
            </h1>

            <p>
                Application de prédiction sportive
                basée sur des données réelles.
            </p>

            <div class="card">

                <h2>Sports</h2>

                <span class="sport">⚽ Football</span>

                <span class="sport">🏀 Basketball</span>

                <span class="sport">🏒 Hockey</span>

            </div>

            <div class="card">

                <h2>⚽ Source football</h2>

                <p>
                    Source actuelle :
                    <strong>OpenFootball</strong>
                </p>

                <p>
                    Les données sont récupérées
                    directement depuis les fichiers
                    publics OpenFootball.
                </p>

                <p>
                    <a href="/api/football/test">
                        🔎 Tester les données football
                    </a>
                </p>

                <p>
                    <a href="/api/football/matches">
                        📋 Voir les matchs
                    </a>
                </p>

            </div>

            <div class="status">

                API :
                <strong>Online</strong>

            </div>

        </div>

    </body>

    </html>
    """
