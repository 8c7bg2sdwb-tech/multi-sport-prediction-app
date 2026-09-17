# Multi-Sport Prediction App

MVP initial : API FastAPI + interface web football.

## Lancer localement
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Le modèle actuel est un baseline Poisson. Il sera remplacé/complété par les modèles entraînés sur données historiques, calibration et backtesting chronologique dans les prochaines étapes.
