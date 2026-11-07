# Jobs étudiants à Roubaix

Application web : recherche d'offres Adzuna autour de Roubaix, adaptation du CV et de la lettre par IA (Gemini), et suivi des candidatures.

## Lancer
1. `python -m venv venv && source venv/bin/activate` (Windows : `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. Copier `.env.example` en `.env` et renseigner `ADZUNA_APP_ID` et `ADZUNA_APP_KEY` ([compte développeur Adzuna](https://developer.adzuna.com/signup)), ainsi que `GEMINI_API_KEY` ([Google AI Studio](https://aistudio.google.com/apikey))
4. `uvicorn main:app --reload` puis ouvrir http://localhost:8000
5. Onglet **Mon profil** : importe un CV PDF, DOCX ou TXT (5 Mo maximum), ou colle son texte, puis vérifie le texte extrait avant de chercher des offres.

## Notes
- L'IA reformule uniquement ce qui est dans ton CV. Relis toujours avant d'envoyer.
- Le CV et l'offre sont transmis à l'API Gemini. Évite d'y inclure des informations sensibles et consulte les conditions de confidentialité de Google.
- L'import de CV extrait le texte localement. Les PDF scannés sans texte sélectionnable ne sont pas pris en charge par l'extraction.
- Adzuna ne fournit pas d'adresse e-mail de recruteur dans ces résultats : ouvre l'annonce pour postuler.
- Les descriptions Adzuna peuvent être des extraits de l'annonce originale.
