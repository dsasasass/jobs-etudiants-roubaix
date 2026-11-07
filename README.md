# Jobs étudiants à Roubaix

Application web : recherche d'offres (API France Travail, rayon autour de Roubaix), adaptation du CV et de la lettre par IA (Claude), envoi par e-mail avec validation, suivi des candidatures.

## Lancer
1. `python -m venv venv && source venv/bin/activate` (Windows : `venv\Scripts\activate`)
2. `pip install -r requirements.txt`
3. Copier `.env.example` en `.env` et remplir les clés (voir commentaires dedans)
4. `uvicorn main:app --reload` puis ouvrir http://localhost:8000
5. Onglet **Mon profil** : coller ton CV complet, puis chercher des offres.

## Notes
- L'IA reformule uniquement ce qui est dans ton CV. Relis toujours avant d'envoyer.
- L'envoi automatique n'est possible que si l'offre donne une adresse e-mail ; sinon le bouton ouvre l'offre.
