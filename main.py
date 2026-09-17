from math import exp, factorial
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Multi-Sport Prediction App", version="0.1.0")

class FootballInput(BaseModel):
    home_team: str
    away_team: str
    home_goals_for: float = Field(0, ge=0)
    home_goals_against: float = Field(0, ge=0)
    away_goals_for: float = Field(0, ge=0)
    away_goals_against: float = Field(0, ge=0)
    home_advantage: float = Field(0.25, ge=0, le=1)
    odds_home: Optional[float] = Field(None, gt=1)
    odds_draw: Optional[float] = Field(None, gt=1)
    odds_away: Optional[float] = Field(None, gt=1)

def poisson(k: int, lam: float) -> float:
    return exp(-lam) * lam**k / factorial(k)

def probabilities(inp: FootballInput):
    home_xg = max(0.05, (inp.home_goals_for + inp.away_goals_against) / 2 + inp.home_advantage)
    away_xg = max(0.05, (inp.away_goals_for + inp.home_goals_against) / 2)
    matrix = {(h, a): poisson(h, home_xg) * poisson(a, away_xg) for h in range(8) for a in range(8)}
    home = sum(p for (h,a),p in matrix.items() if h>a)
    draw = sum(p for (h,a),p in matrix.items() if h==a)
    away = sum(p for (h,a),p in matrix.items() if h<a)
    btts = sum(p for (h,a),p in matrix.items() if h>0 and a>0)
    over25 = sum(p for (h,a),p in matrix.items() if h+a>=3)
    scores = sorted(matrix.items(), key=lambda x:x[1], reverse=True)[:5]
    return {
        "expected_goals": round(home_xg + away_xg, 3),
        "probabilities": {
            "home": round(home,4), "draw": round(draw,4), "away": round(away,4),
            "btts_yes": round(btts,4), "over_2_5": round(over25,4),
            "under_2_5": round(1-over25,4)
        },
        "top_scores": [
            {"score": f"{h}-{a}", "probability": round(p,4)}
            for (h,a),p in scores
        ]
    }

@app.get("/health")
def health():
    return {"status":"ok"}

@app.post("/api/predict/football")
def predict_football(inp: FootballInput):
    result = probabilities(inp)
    if inp.odds_home and inp.odds_draw and inp.odds_away:
        raw = [1/inp.odds_home, 1/inp.odds_draw, 1/inp.odds_away]
        total = sum(raw)
        market = [x/total for x in raw]
        model = [result["probabilities"]["home"], result["probabilities"]["draw"], result["probabilities"]["away"]]
        result["market_probabilities"] = {
            "home":round(market[0],4), "draw":round(market[1],4), "away":round(market[2],4)
        }
        result["edge"] = {
            k:round(model[i]-market[i],4)
            for i,k in enumerate(["home","draw","away"])
        }
    return result

@app.get("/", response_class=HTMLResponse)
def home():
    return '''<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Multi-Sport Prediction</title>
<style>
body{font-family:system-ui;margin:0;background:#0b1020;color:#eef2ff}
main{max-width:900px;margin:auto;padding:32px}h1{font-size:34px}
p{color:#aab4d0}.card{background:#151c33;border:1px solid #283252;border-radius:18px;padding:22px;margin:16px 0}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
input{width:100%;box-sizing:border-box;padding:12px;border-radius:10px;border:1px solid #3a4668;background:#0d1428;color:white}
button{margin-top:16px;padding:13px 18px;border:0;border-radius:10px;cursor:pointer}
pre{white-space:pre-wrap;color:#cbd5e1}@media(max-width:650px){.grid{grid-template-columns:1fr}}
</style></head><body><main><h1>🏆 Multi-Sport Prediction</h1>
<p>MVP — football d'abord, architecture prête pour basketball et hockey.</p>
<div class="card"><h2>⚽ Analyse football</h2><div class="grid">
<input id="home" placeholder="Équipe domicile"><input id="away" placeholder="Équipe extérieur">
<input id="hgf" type="number" step="0.01" placeholder="Buts marqués domicile">
<input id="hga" type="number" step="0.01" placeholder="Buts encaissés domicile">
<input id="agf" type="number" step="0.01" placeholder="Buts marqués extérieur">
<input id="aga" type="number" step="0.01" placeholder="Buts encaissés extérieur">
</div><button onclick="predict()">Analyser</button><pre id="out"></pre></div>
</main><script>
async function predict(){let n=id=>document.getElementById(id).value;
let body={home_team:n('home'),away_team:n('away'),home_goals_for:+n('hgf')||0,
home_goals_against:+n('hga')||0,away_goals_for:+n('agf')||0,away_goals_against:+n('aga')||0};
let r=await fetch('/api/predict/football',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
document.getElementById('out').textContent=JSON.stringify(await r.json(),null,2)}
</script></body></html>'''
