
import json
import urllib.request
from math import exp, factorial
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Football Prediction Engine")

BASE_URL = (
    "https://raw.githubusercontent.com/"
    "openfootball/football.json/master"
)


@lru_cache(maxsize=20)
def load_matches(season: str, league_file: str):
    if "/" in season or ".." in season:
        raise ValueError("Saison invalide")

    if "/" in league_file or ".." in league_file:
        raise ValueError("Fichier de ligue invalide")

    url = f"{BASE_URL}/{season}/{league_file}"

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "FootballPredictionEngine"}
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    matches = []

    for match in data.get("matches", []):
        score_data = match.get("score")

        if not isinstance(score_data, dict):
            continue

        score = score_data.get("ft")

        if not isinstance(score, list) or len(score) != 2:
            continue

        try:
            home_goals = int(score[0])
            away_goals = int(score[1])
        except (ValueError, TypeError):
            continue

        if not match.get("team1") or not match.get("team2"):
            continue

        matches.append({
            "date": match.get("date"),
            "home": match["team1"],
            "away": match["team2"],
            "home_goals": home_goals,
            "away_goals": away_goals,
        })

    return matches
    

class PredictionInput(BaseModel):
    home_team: str = Field(min_length=1)
    away_team: str = Field(min_length=1)
    season: str = "2026-27"
    league_file: str = "en.1.json"

    odds_home: Optional[float] = None
    odds_draw: Optional[float] = None
    odds_away: Optional[float] = None


def poisson(lmbda, goals):
    return exp(-lmbda) * (lmbda ** goals) / factorial(goals)


def get_team_statistics(matches, team):
    home_games = [
        m for m in matches if m["home"] == team
    ]

    away_games = [
        m for m in matches if m["away"] == team
    ]

    return {
        "home_played": len(home_games),
        "away_played": len(away_games),
        "home_scored": sum(
            m["home_goals"] for m in home_games
        ),
        "home_conceded": sum(
            m["away_goals"] for m in home_games
        ),
        "away_scored": sum(
            m["away_goals"] for m in away_games
        ),
        "away_conceded": sum(
            m["home_goals"] for m in away_games
        ),
    }

def get_team_strength(matches, team):
    stats = get_team_statistics(matches, team)

    home_played = stats["home_played"]
    away_played = stats["away_played"]

    league_home_avg = (
        sum(m["home_goals"] for m in matches) / len(matches)
    )

    league_away_avg = (
        sum(m["away_goals"] for m in matches) / len(matches)
    )

    home_scored_avg = (
        stats["home_scored"] / home_played
        if home_played else None
    )

    home_conceded_avg = (
        stats["home_conceded"] / home_played
        if home_played else None
    )

    away_scored_avg = (
        stats["away_scored"] / away_played
        if away_played else None
    )

    away_conceded_avg = (
        stats["away_conceded"] / away_played
        if away_played else None
    )

    return {
        "team": team,
        "matches": {
            "home": home_played,
            "away": away_played
        },
        "home": {
            "goals_scored_avg": round(home_scored_avg, 2)
            if home_scored_avg is not None else None,
            "goals_conceded_avg": round(home_conceded_avg, 2)
            if home_conceded_avg is not None else None,
            "attack_index": round(
                home_scored_avg / league_home_avg, 3
            ) if home_scored_avg is not None and league_home_avg else None,
            "defense_index": round(
                league_away_avg / home_conceded_avg, 3
            ) if home_conceded_avg is not None and home_conceded_avg > 0 else None
        },
        "away": {
            "goals_scored_avg": round(away_scored_avg, 2)
            if away_scored_avg is not None else None,
            "goals_conceded_avg": round(away_conceded_avg, 2)
            if away_conceded_avg is not None else None,
            "attack_index": round(
                away_scored_avg / league_away_avg, 3
            ) if away_scored_avg is not None and league_away_avg else None,
            "defense_index": round(
                league_home_avg / away_conceded_avg, 3
            ) if away_conceded_avg is not None and away_conceded_avg > 0 else None
        }
    }

def get_recent_form(matches, team, last_n=5):
    team_matches = [
        m for m in matches
        if m["home"] == team or m["away"] == team
    ]

    team_matches = sorted(
        team_matches,
        key=lambda m: m.get("date") or "",
        reverse=True
    )[:last_n]

    wins = 0
    draws = 0
    losses = 0
    goals_scored = 0
    goals_conceded = 0
    points = 0
    form = []

    for match in team_matches:
        if match["home"] == team:
            scored = match["home_goals"]
            conceded = match["away_goals"]
        else:
            scored = match["away_goals"]
            conceded = match["home_goals"]

        goals_scored += scored
        goals_conceded += conceded

        if scored > conceded:
            wins += 1
            points += 3
            result = "W"

        elif scored == conceded:
            draws += 1
            points += 1
            result = "D"

        else:
            losses += 1
            result = "L"

        form.append({
            "date": match.get("date"),
            "result": result,
            "goals_scored": scored,
            "goals_conceded": conceded
        })

    return {
        "matches_analyzed": len(team_matches),
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "points": points,
        "goals_scored": goals_scored,
        "goals_conceded": goals_conceded,
        "form": form
    }
def calculate_prediction(data):
    try:
        matches = load_matches(
            data.season,
            data.league_file
        )
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Impossible de récupérer OpenFootball : {error}"
        )

    if len(matches) < 10:
        raise HTTPException(
            status_code=422,
            detail="Pas assez de matchs historiques."
        )

    home_stats = get_team_statistics(
        matches, data.home_team
    )

    away_stats = get_team_statistics(
        matches, data.away_team
    )

    if home_stats["home_played"] < 2:
        raise HTTPException(
            status_code=422,
            detail="Pas assez de matchs à domicile pour cette équipe."
        )

    if away_stats["away_played"] < 2:
        raise HTTPException(
            status_code=422,
            detail="Pas assez de matchs à l'extérieur pour cette équipe."
        )

    league_home_avg = sum(
        m["home_goals"] for m in matches
    ) / len(matches)

    league_away_avg = sum(
        m["away_goals"] for m in matches
    ) / len(matches)

    if league_home_avg <= 0 or league_away_avg <= 0:
        raise HTTPException(
            status_code=422,
            detail="Moyennes de ligue invalides."
        )

    home_scored_avg = (
        home_stats["home_scored"]
        / home_stats["home_played"]
    )

    home_conceded_avg = (
        home_stats["home_conceded"]
        / home_stats["home_played"]
    )

    away_scored_avg = (
        away_stats["away_scored"]
        / away_stats["away_played"]
    )

    away_conceded_avg = (
        away_stats["away_conceded"]
        / away_stats["away_played"]
    )

    expected_home = (
        home_scored_avg
        * away_conceded_avg
        / league_home_avg
    )

    expected_away = (
        away_scored_avg
        * home_conceded_avg
        / league_away_avg
    )

    expected_home = max(0.05, expected_home)
    expected_away = max(0.05, expected_away)

    home_win = 0
    draw = 0
    away_win = 0
    btts_yes = 0
    under_25 = 0
    scores = []

    for h in range(10):
        for a in range(10):
            probability = (
                poisson(expected_home, h)
                * poisson(expected_away, a)
            )

            scores.append({
                "score": f"{h}-{a}",
                "probability": probability
            })

            if h > a:
                home_win += probability
            elif h == a:
                draw += probability
            else:
                away_win += probability

            if h > 0 and a > 0:
                btts_yes += probability

            if h + a < 3:
                under_25 += probability

    over_25 = 1 - under_25

    scores.sort(
        key=lambda x: x["probability"],
        reverse=True
    )

    value_analysis = None

    odds = [
        data.odds_home,
        data.odds_draw,
        data.odds_away
    ]

    if all(x is not None and x > 1 for x in odds):
        raw = [1 / x for x in odds]
        total = sum(raw)
        market = [x / total for x in raw]

        model = [home_win, draw, away_win]

        value_analysis = {}

        for name, probability, market_prob, odd in zip(
            ["home", "draw", "away"],
            model,
            market,
            odds
        ):
            value_analysis[name] = {
                "model_probability": round(probability, 4),
                "market_probability": round(market_prob, 4),
                "edge": round(probability - market_prob, 4),
                "ev": round(probability * odd - 1, 4)
            }

    return {
        "teams": {
            "home": data.home_team,
            "away": data.away_team
        },
        "data_source": "OpenFootball",
        "historical_matches": len(matches),
        "expected_goals": {
            "home": round(expected_home, 3),
            "away": round(expected_away, 3),
            "total": round(expected_home + expected_away, 3)
        },
        "probabilities": {
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "btts_yes": round(btts_yes, 4),
            "btts_no": round(1 - btts_yes, 4),
            "under_2_5": round(under_25, 4),
            "over_2_5": round(over_25, 4)
        },
        "top_scores": [
            {
                "score": x["score"],
                "probability": round(x["probability"], 4)
            }
            for x in scores[:5]
        ],
        "value_analysis": value_analysis
    }

def run_backtest(matches, min_history=30):
    ordered = sorted(
        matches,
        key=lambda m: m.get("date") or ""
    )

    results = []

    for index in range(min_history, len(ordered)):
        historical = ordered[:index]
        match = ordered[index]

        home = match["home"]
        away = match["away"]

        home_stats = get_team_statistics(historical, home)
        away_stats = get_team_statistics(historical, away)

        if (
            home_stats["home_played"] < 2
            or away_stats["away_played"] < 2
        ):
            continue

        league_home_avg = sum(
            m["home_goals"] for m in historical
        ) / len(historical)

        league_away_avg = sum(
            m["away_goals"] for m in historical
        ) / len(historical)

        if league_home_avg <= 0 or league_away_avg <= 0:
            continue

        expected_home = (
            home_stats["home_scored"]
            / home_stats["home_played"]
            * (
                away_stats["away_conceded"]
                / away_stats["away_played"]
            )
            / league_home_avg
        )

        expected_away = (
            away_stats["away_scored"]
            / away_stats["away_played"]
            * (
                home_stats["home_conceded"]
                / home_stats["home_played"]
            )
            / league_away_avg
        )

        expected_home = max(0.05, expected_home)
        expected_away = max(0.05, expected_away)

        home_win = 0
        draw = 0
        away_win = 0

        for h in range(10):
            for a in range(10):
                probability = (
                    poisson(expected_home, h)
                    * poisson(expected_away, a)
                )

                if h > a:
                    home_win += probability
                elif h == a:
                    draw += probability
                else:
                    away_win += probability

        probabilities = {
            "home": home_win,
            "draw": draw,
            "away": away_win
        }

        prediction = max(
            probabilities,
            key=probabilities.get
        )

        if match["home_goals"] > match["away_goals"]:
            actual = "home"
        elif match["home_goals"] == match["away_goals"]:
            actual = "draw"
        else:
            actual = "away"

        results.append({
            "date": match.get("date"),
            "home": home,
            "away": away,
            "predicted": prediction,
            "actual": actual,
            "correct": prediction == actual
        })

    total = len(results)
    correct = sum(r["correct"] for r in results)

    return {
        "matches_tested": total,
        "correct_predictions": correct,
        "accuracy": round(correct / total, 4) if total else None,
        "results": results
    }
@app.get("/api/football/backtest")
def football_backtest(
    season: str = "2025-26",
    league_file: str = "en.1.json",
    min_history: int = 30
):
    matches = load_matches(season, league_file)

    results = run_backtest(
        matches,
        min_history=min_history
    )

    return {
        "status": "success",
        "source": "OpenFootball",
        "season": season,
        "league_file": league_file,
        **results
    }
@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": "football-prediction-engine"
    }


@app.get("/api/football/test")
def test_data(
    season: str = "2026-27",
    league_file: str = "en.1.json"
):
    try:
        matches = load_matches(season, league_file)
        return {
            "status": "success",
            "source": "OpenFootball",
            "season": season,
            "league": league_file,
            "completed_matches": len(matches)
        }
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )


@app.get("/api/football/teams")
def teams(
    season: str = "2026-27",
    league_file: str = "en.1.json"
):
    try:
        matches = load_matches(season, league_file)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=str(error)
        )

    names = sorted(set(
        [m["home"] for m in matches]
        + [m["away"] for m in matches]
    ))

    return {"teams": names}

@app.get("/api/football/strength")
def team_strength(
    team: str,
    season: str = "2025-26",
    league_file: str = "en.1.json"
):
    try:
        matches = load_matches(season, league_file)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur OpenFootball : {error}"
        )

    if not matches:
        raise HTTPException(
            status_code=422,
            detail="Aucun match disponible."
        )

    if team not in (
        [m["home"] for m in matches]
        + [m["away"] for m in matches]
    ):
        raise HTTPException(
            status_code=404,
            detail="Équipe introuvable dans cette saison."
        )

    return {
        "season": season,
        "strength": get_team_strength(matches, team)
    }

@app.get("/api/football/form")
def team_form(
    team: str,
    season: str = "2025-26",
    league_file: str = "en.1.json"
):
    try:
        matches = load_matches(season, league_file)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur OpenFootball : {error}"
        )

    if team not in [
        m["home"] for m in matches
    ] + [
        m["away"] for m in matches
    ]:
        raise HTTPException(
            status_code=404,
            detail="Équipe introuvable dans cette saison."
        )

    return {
        "team": team,
        "season": season,
        "recent_form": get_recent_form(matches, team, 5)
    }
@app.get("/api/football/statistics")
def league_statistics(
    season: str = "2025-26",
    league_file: str = "en.1.json"
):
    try:
        matches = load_matches(season, league_file)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur de récupération des données : {error}"
        )

    teams = sorted(set(
        [m["home"] for m in matches]
        + [m["away"] for m in matches]
    ))

    results = []

    for team in teams:
        stats = get_team_statistics(matches, team)

        home_played = stats["home_played"]
        away_played = stats["away_played"]
        played = home_played + away_played

        goals_scored = (
            stats["home_scored"]
            + stats["away_scored"]
        )

        goals_conceded = (
            stats["home_conceded"]
            + stats["away_conceded"]
        )

        results.append({
            "team": team,
            "played": played,
            "home_played": home_played,
            "away_played": away_played,
            "goals_scored": goals_scored,
            "goals_conceded": goals_conceded,
            "average_scored": round(
                goals_scored / played, 2
            ) if played else 0,
            "average_conceded": round(
                goals_conceded / played, 2
            ) if played else 0
        })

    return {
        "status": "success",
        "season": season,
        "league": league_file,
        "teams_count": len(results),
        "statistics": results
    }
@app.post("/api/predict/football")
def predict_football(data: PredictionInput):
    if data.home_team.strip().lower() == data.away_team.strip().lower():
        raise HTTPException(
            status_code=422,
            detail="Les deux équipes doivent être différentes."
        )

    return calculate_prediction(data)


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport"
            content="width=device-width, initial-scale=1">
      <title>Football Prediction Engine</title>
      <style>
        body {
          background:#0f172a;
          color:white;
          font-family:Arial;
          padding:30px;
          max-width:800px;
          margin:auto;
        }
        .card {
          background:#1e293b;
          padding:20px;
          border-radius:14px;
          margin-top:20px;
        }
      </style>
    </head>
    <body>
      <h1>⚽ Football Prediction Engine</h1>
      <div class="card">
        <h2>Moteur statistique</h2>
        <p>Source : OpenFootball</p>
        <p>Modèle : Poisson</p>
        <p>Analyse : 1N2, BTTS et Over/Under 2.5</p>
        <p>Les cotes servent uniquement à mesurer
        l'edge et l'espérance de valeur.</p>
      </div>
      <div class="card">
        <h2>Prochaines étapes</h2>
        <p>Calibration, backtesting et filtres de qualité.</p>
      </div>
    </body>
    </html>
    """
