from math import exp, factorial
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


app = FastAPI(title="Multi-Sport Prediction App")


class FootballInput(BaseModel):
    home_team: str
    away_team: str

    home_goals_for: float
    home_goals_against: float

    away_goals_for: float
    away_goals_against: float

    home_advantage: float = 0.15

    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None


def poisson_probability(lmbda: float, k: int) -> float:
    return exp(-lmbda) * (lmbda ** k) / factorial(k)


def calculate_prediction(data: FootballInput):
    home_attack = data.home_goals_for
    home_defense = data.home_goals_against

    away_attack = data.away_goals_for
    away_defense = data.away_goals_against

    expected_home = max(
        0.05,
        (home_attack + away_defense) / 2 + data.home_advantage,
    )

    expected_away = max(
        0.05,
        (away_attack + home_defense) / 2,
    )

    home_win = 0.0
    draw = 0.0
    away_win = 0.0

    score_probabilities = []

    for home_goals in range(0, 8):
        for away_goals in range(0, 8):
            probability = (
                poisson_probability(expected_home, home_goals)
                * poisson_probability(expected_away, away_goals)
            )

            score_probabilities.append(
                {
                    "home_goals": home_goals,
                    "away_goals": away_goals,
                    "probability": probability,
                }
            )

            if home_goals > away_goals:
                home_win += probability
            elif home_goals == away_goals:
                draw += probability
            else:
                away_win += probability

    btts_yes = 1 - (
        poisson_probability(expected_home, 0)
        + poisson_probability(expected_away, 0)
        - (
            poisson_probability(expected_home, 0)
            * poisson_probability(expected_away, 0)
        )
    )

    total_lambda = expected_home + expected_away

    under_25 = sum(
        poisson_probability(total_lambda, total_goals)
        for total_goals in range(0, 3)
    )

    over_25 = 1 - under_25

    score_probabilities.sort(
        key=lambda x: x["probability"],
        reverse=True,
    )

    top_scores = score_probabilities[:5]

    result = max(
        [
            ("1", home_win),
            ("X", draw),
            ("2", away_win),
        ],
        key=lambda x: x[1],
    )

    value = None

    if (
        data.odds_home
        and data.odds_draw
        and data.odds_away
    ):
        market_home = 1 / data.odds_home
        market_draw = 1 / data.odds_draw
        market_away = 1 / data.odds_away

        total_market = (
            market_home + market_draw + market_away
        )

        market_home /= total_market
        market_draw /= total_market
        market_away /= total_market

        value = {
            "home": {
                "market_probability": market_home,
                "model_probability": home_win,
                "edge": home_win - market_home,
                "ev": home_win * data.odds_home - 1,
            },
            "draw": {
                "market_probability": market_draw,
                "model_probability": draw,
                "edge": draw - market_draw,
                "ev": draw * data.odds_draw - 1,
            },
            "away": {
                "market_probability": market_away,
                "model_probability": away_win,
                "edge": away_win - market_away,
                "ev": away_win * data.odds_away - 1,
            },
        }

    return {
        "home_team": data.home_team,
        "away_team": data.away_team,
        "expected_goals": {
            "home": round(expected_home, 3),
            "away": round(expected_away, 3),
            "total": round(
                expected_home + expected_away,
                3,
            ),
        },
        "probabilities": {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "btts_yes": round(btts_yes, 4),
            "btts_no": round(1 - btts_yes, 4),
            "over_2_5": round(over_25, 4),
            "under_2_5": round(under_25, 4),
        },
        "prediction": {
            "result": result[0],
            "result_probability": round(result[1], 4),
        },
        "top_exact_scores": [
            {
                "score": f"{x['home_goals']}-{x['away_goals']}",
                "probability": round(
                    x["probability"],
                    4,
                ),
            }
            for x in top_scores
        ],
        "value_analysis": value,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "multi-sport-prediction-app",
    }


@app.post("/api/predict/football")
def predict_football(data: FootballInput):
    return calculate_prediction(data)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport"
              content="width=device-width, initial-scale=1.0">

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
                margin-right: 8px;
                border-radius: 10px;
                background: #334155;
            }

            .status {
                margin-top: 25px;
                padding: 15px;
                background: #334155;
                border-radius: 10px;
            }
        </style>
    </head>

    <body>
        <div class="container">

            <h1>
                🏆 Multi-Sport Prediction App
            </h1>

            <p>
                Analyse statistique football,
                basketball et hockey.
            </p>

            <div class="card">
                <h2>Sports</h2>

                <span class="sport">⚽ Football</span>
                <span class="sport">🏀 Basketball</span>
                <span class="sport">🏒 Hockey</span>
            </div>

            <div class="card">
                <h2>⚽ Football</h2>

                <p>
                    Baseline statistique actuellement
                    basée sur un modèle de Poisson.
                </p>

                <p>
                    Les prochaines étapes intégreront
                    les données historiques, les modèles
                    entraînés, la calibration et le
                    backtesting chronologique.
                </p>
            </div>

            <div class="status">
                API : <strong>Online</strong>
            </div>

        </div>
    </body>
    </html>
    """
