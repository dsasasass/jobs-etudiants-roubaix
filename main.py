import json
import os
import sqlite3
from datetime import date

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from google import genai
from google.genai import errors, types
from pydantic import BaseModel

load_dotenv()
E = os.environ.get
app = FastAPI(title="Jobs étudiants Roubaix")
db = sqlite3.connect("data.db", check_same_thread=False)
db.execute("create table if not exists kv(k text primary key, v text)")
db.execute("create table if not exists cand(id integer primary key, offre_id text, titre text, entreprise text, statut text, jour text)")
ADZUNA_API = "https://api.adzuna.com/v1/api/jobs/fr/search/1"


def kv_get(k, default=""):
    r = db.execute("select v from kv where k=?", (k,)).fetchone()
    return r[0] if r else default


@app.get("/api/offres")
def offres(q: str = "étudiant", distance: int = 15):
    app_id, app_key = E("ADZUNA_APP_ID"), E("ADZUNA_APP_KEY")
    if not app_id or not app_key:
        raise HTTPException(503, "Configure ADZUNA_APP_ID et ADZUNA_APP_KEY dans le fichier .env.")
    if not 1 <= distance <= 30:
        raise HTTPException(422, "Le rayon doit être compris entre 1 et 30 km.")
    try:
        response = httpx.get(
            ADZUNA_API,
            params={
                "app_id": app_id,
                "app_key": app_key,
                "results_per_page": 50,
                "what": q,
                "where": "Roubaix",
                "distance": distance,
                "sort_by": "date",
                "content-type": "application/json",
            },
            timeout=30,
        )
    except httpx.HTTPError as ex:
        raise HTTPException(502, "Connexion à Adzuna impossible. Réessaie dans quelques instants.") from ex
    if response.status_code != 200:
        raise HTTPException(
            502,
            f"Adzuna a refusé la recherche (HTTP {response.status_code}). Vérifie tes identifiants et ton quota.",
        )
    try:
        payload = response.json()
    except ValueError as ex:
        raise HTTPException(502, "Réponse Adzuna illisible. Réessaie dans quelques instants.") from ex
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise HTTPException(502, "La réponse Adzuna ne contient pas la liste des offres attendue.")

    out = []
    for offer in payload["results"]:
        if not isinstance(offer, dict):
            raise HTTPException(502, "Adzuna a renvoyé une offre au format inattendu.")
        company = offer.get("company") or {}
        location = offer.get("location") or {}
        contract = offer.get("contract_time") or offer.get("contract_type") or ""
        created = offer.get("created") or ""
        out.append({
            "id": str(offer.get("id", "")),
            "titre": offer.get("title", ""),
            "entreprise": company.get("display_name", "") if isinstance(company, dict) else "",
            "lieu": location.get("display_name", "") if isinstance(location, dict) else "",
            "contrat": contract.replace("_", " ") if isinstance(contract, str) else "",
            "date": created[:10] if isinstance(created, str) else "",
            "description": offer.get("description", ""),
            "url": offer.get("redirect_url", ""),
        })
    return out


class Profil(BaseModel):
    nom: str
    cv: str


@app.get("/api/profil")
def get_profil():
    return {"nom": kv_get("nom"), "cv": kv_get("cv")}


@app.post("/api/profil")
def set_profil(p: Profil):
    for k, v in (("nom", p.nom), ("cv", p.cv)):
        db.execute("insert or replace into kv values(?,?)", (k, v))
    db.commit()
    return {"ok": True}


class Offre(BaseModel):
    titre: str
    entreprise: str = ""
    description: str = ""


@app.post("/api/adapter")
def adapter(o: Offre):
    cv = kv_get("cv")
    if not cv:
        raise HTTPException(400, "Enregistre d'abord ton CV dans l'onglet Profil.")
    api_key = E("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(503, "Configure GEMINI_API_KEY dans le fichier .env pour adapter ton CV.")
    prompt = f"""Tu aides un étudiant à candidater à un job étudiant en France.
CV de référence :
{cv}

Offre : {o.titre} chez {o.entreprise}
{o.description[:3000]}

Règles : n'invente AUCUNE expérience, diplôme ou compétence absents du CV. Reformule et réordonne le CV pour mettre en avant ce qui correspond à l'offre (une page max).
Rédige une lettre de motivation courte (150-200 mots), sincère, en français, signée {kv_get('nom')}.
Réponds uniquement en JSON : {{"cv": "texte du CV adapté", "lettre": "texte de la lettre"}}"""
    with genai.Client(api_key=api_key) as client:
        try:
            response = client.models.generate_content(
                model=E("GEMINI_MODEL", "gemini-3.5-flash-lite"),
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=2500,
                    response_mime_type="application/json",
                ),
            )
        except errors.APIError as ex:
            raise HTTPException(
                502,
                f"Erreur Gemini (HTTP {ex.code}). Vérifie GEMINI_API_KEY, GEMINI_MODEL et le quota de l'API.",
            ) from ex
    if not response.text:
        raise HTTPException(502, "Gemini n'a pas renvoyé de texte. Relance la génération.")
    try:
        return json.loads(response.text.strip())
    except ValueError as ex:
        raise HTTPException(502, "Réponse IA illisible, relance la génération.") from ex


class Suivi(BaseModel):
    offre_id: str
    titre: str
    entreprise: str = ""
    statut: str = "postulée"


@app.post("/api/candidatures")
def marquer(s: Suivi):
    db.execute(
        "insert into cand(offre_id,titre,entreprise,statut,jour) values(?,?,?,?,?)",
        (s.offre_id, s.titre, s.entreprise, s.statut, date.today().isoformat()),
    )
    db.commit()
    return {"ok": True}


@app.get("/api/candidatures")
def liste():
    return [
        dict(zip(("id", "offre_id", "titre", "entreprise", "statut", "jour"), r))
        for r in db.execute("select * from cand order by id desc")
    ]


@app.get("/")
def home():
    return FileResponse("static/index.html")
