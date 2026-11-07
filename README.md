# Jobs étudiants à Roubaix

Application web : recherche d'offres (API France Travail, rayon autour de Roubaix), adaptation du CV et de la lettre par IA (Gemini), envoi par e-mail avec validation, suivi des candidatures.

## Lancer
1. `python -m venv venv && source venv/bin/activate` (Windows : `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. Copier `.env.example` en `.env` et remplir les clés France Travail, `GEMINI_API_KEY` (à créer sur [Google AI Studio](https://aistudio.google.com/apikey)) et, si nécessaire, les paramètres SMTP (voir commentaires dedans)
4. `uvicorn main:app --reload` puis ouvrir http://localhost:8000
5. Onglet **Mon profil** : coller ton CV complet, puis chercher des offres.

## Notes
- L'IA reformule uniquement ce qui est dans ton CV. Relis toujours avant d'envoyer.
- Le CV et l'offre sont transmis à l'API Gemini. Évite d'y inclure des informations sensibles et consulte les conditions de confidentialité de Google.
- L'envoi automatique n'est possible que si l'offre donne une adresse e-mail ; sinon le bouton ouvre l'offre.
