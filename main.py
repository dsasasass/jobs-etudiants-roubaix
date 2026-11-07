import os, io, json, time, sqlite3, smtplib
from datetime import date
from email.message import EmailMessage
import httpx
from google import genai
from google.genai import errors, types
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape

load_dotenv()
E = os.environ.get
app = FastAPI(title="Jobs étudiants Roubaix")
db = sqlite3.connect("data.db", check_same_thread=False)
db.execute("create table if not exists kv(k text primary key, v text)")
db.execute("create table if not exists cand(id integer primary key, offre_id text, titre text, entreprise text, statut text, jour text)")
FT_AUTH = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire"
FT_API = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
ROUBAIX = "59512"  # code INSEE
_tok = {"v": None, "exp": 0}


def token():
    if time.time() < _tok["exp"]:
        return _tok["v"]
    r = httpx.post(FT_AUTH, data={"grant_type": "client_credentials", "client_id": E("FT_CLIENT_ID"),
                   "client_secret": E("FT_CLIENT_SECRET"), "scope": "api_offresdemploi_v2 o2dsoffre"})
    if r.status_code != 200:
        raise HTTPException(502, "Connexion France Travail refusée : vérifie FT_CLIENT_ID et FT_CLIENT_SECRET dans .env")
    j = r.json()
    _tok.update(v=j["access_token"], exp=time.time() + j["expires_in"] - 30)
    return _tok["v"]


def kv_get(k, default=""):
    r = db.execute("select v from kv where k=?", (k,)).fetchone()
    return r[0] if r else default


@app.get("/api/offres")
def offres(q: str = "étudiant", distance: int = 15):
    r = httpx.get(FT_API, headers={"Authorization": f"Bearer {token()}"}, timeout=30,
                  params={"commune": ROUBAIX, "distance": distance, "motsCles": q, "range": "0-49"})
    if r.status_code in (204, 206) and not r.content:
        return []
    out = []
    for o in r.json().get("resultats", []):
        c = o.get("contact") or {}
        mail = c.get("courriel") or ""
        if "@" not in mail:
            mail = next((w for w in (c.get("coordonnees1") or "").split() if "@" in w), "")
        out.append({"id": o["id"], "titre": o.get("intitule", ""), "entreprise": (o.get("entreprise") or {}).get("nom", ""),
                    "lieu": (o.get("lieuTravail") or {}).get("libelle", ""), "contrat": o.get("typeContratLibelle", ""),
                    "date": (o.get("dateCreation") or "")[:10], "description": o.get("description", ""),
                    "url": (o.get("origineOffre") or {}).get("urlOrigine", ""), "email": mail.strip("<>.,;")})
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
    try:
        response = genai.Client(api_key=api_key).models.generate_content(
            model=E("GEMINI_MODEL", "gemini-3.1-flash-lite-preview"),
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
    txt = response.text.strip()
    try:
        return json.loads(txt)
    except ValueError:
        raise HTTPException(502, "Réponse IA illisible, relance la génération.")


def pdf(text, title):
    buf, st = io.BytesIO(), getSampleStyleSheet()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=title, leftMargin=50, rightMargin=50, topMargin=50, bottomMargin=50)
    doc.build([x for l in text.split("\n") for x in (Paragraph(escape(l) or "&nbsp;", st["BodyText"]), Spacer(1, 2))])
    return buf.getvalue()


class Envoi(BaseModel):
    offre_id: str
    titre: str
    entreprise: str = ""
    email: str
    cv: str
    lettre: str


@app.post("/api/envoyer")
def envoyer(e: Envoi):
    nom = kv_get("nom")
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = f"Candidature : {e.titre} - {nom}", E("SMTP_USER"), e.email
    msg.set_content(e.lettre)
    msg.add_attachment(pdf(e.cv, "CV"), maintype="application", subtype="pdf", filename=f"CV_{nom.replace(' ', '_')}.pdf")
    try:
        with smtplib.SMTP_SSL(E("SMTP_HOST"), int(E("SMTP_PORT", "465"))) as s:
            s.login(E("SMTP_USER"), E("SMTP_PASS"))
            s.send_message(msg)
    except Exception as ex:
        raise HTTPException(502, f"Envoi impossible : {ex}")
    return marquer(Suivi(offre_id=e.offre_id, titre=e.titre, entreprise=e.entreprise, statut="envoyée par e-mail"))


class Suivi(BaseModel):
    offre_id: str
    titre: str
    entreprise: str = ""
    statut: str = "postulée"


@app.post("/api/candidatures")
def marquer(s: Suivi):
    db.execute("insert into cand(offre_id,titre,entreprise,statut,jour) values(?,?,?,?,?)",
               (s.offre_id, s.titre, s.entreprise, s.statut, date.today().isoformat()))
    db.commit()
    return {"ok": True}


@app.get("/api/candidatures")
def liste():
    return [dict(zip(("id", "offre_id", "titre", "entreprise", "statut", "jour"), r))
            for r in db.execute("select * from cand order by id desc")]


@app.get("/")
def home():
    return FileResponse("static/index.html")
