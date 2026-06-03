# SODEXAM — Comptes partagés (correctif)

## Le problème que tu rencontrais
Les comptes étaient stockés **dans le navigateur** (localStorage), donc chaque
poste avait ses propres comptes isolés. Les identifiants créés chez toi ne
fonctionnaient nulle part ailleurs, et disparaissaient si tu changeais de
navigateur ou vidais le cache.

## Ce qui change
L'authentification est désormais **gérée par le serveur** (`serveur.py`). Les
comptes sont enregistrés côté serveur et partagés par toutes les stations : un
identifiant créé dans *Administration* fonctionne immédiatement depuis
n'importe quel ordinateur.

## ⚠️ Important pour Render (offre gratuite)
Sur Render gratuit, le disque est **éphémère** : la base de données est effacée
à chaque redéploiement et après chaque mise en veille. Pour que tes comptes
soient **permanents**, définis la variable d'environnement `SODEXAM_ACCOUNTS` :
le serveur recrée ces comptes automatiquement à chaque démarrage.

### Étapes sur Render
1. Pousse `serveur.py`, `app.html`, `requirements.txt` sur ton dépôt GitHub.
2. Dans Render → ton service → **Settings → Build & Deploy** :
   - **Start Command** : `gunicorn serveur:app`
     (ou `python serveur.py` — les deux fonctionnent)
3. Dans **Environment**, ajoute ces variables :

   | Clé | Valeur |
   |-----|--------|
   | `SODEXAM_SECRET` | une longue chaîne secrète stable (ex. `chaine-aleatoire-a-changer`) |
   | `SODEXAM_ACCOUNTS` | la liste JSON de tes comptes (voir ci-dessous) |
   | `SODEXAM_ADMIN_KEY` | (optionnel) doit rester identique à `SUIVI_ADMIN_KEY` dans `app.html` |

4. Exemple de valeur pour `SODEXAM_ACCOUNTS` (sur une seule ligne) :

   ```json
   [{"username":"admin","password":"TonMotDePasseAdmin","role":"admin","station":"Administration"},
    {"username":"abidjan","password":"abj2024","role":"station","station":"Abidjan"},
    {"username":"bouake","password":"bke2024","role":"station","station":"Bouaké"}]
   ```

5. Redéploie. Les comptes ci-dessus seront recréés à chaque démarrage.

> Sans `SODEXAM_ACCOUNTS`, un compte `admin` / `admin123` est créé par défaut,
> mais il sera réinitialisé à chaque redémarrage de Render. Définir la variable
> est donc fortement recommandé.

## Gestion des comptes dans l'application
- Onglet **Administration** : créer, supprimer, lister les comptes (admin).
- **Exporter les comptes** : télécharge la liste (sans les mots de passe) comme sauvegarde.
- **Importer des comptes** : crée en lot à partir d'un fichier JSON au format
  `[{"username":"...","password":"...","role":"station","station":"..."}]`.
- Les comptes créés *en cours d'utilisation* ne survivent pas à un redémarrage
  de Render **sauf** s'ils figurent aussi dans `SODEXAM_ACCOUNTS`. Pour des
  comptes durables, ajoute-les à cette variable.

## Sécurité
- Les mots de passe sont hachés (PBKDF2-SHA256) côté serveur ; ils ne sont
  jamais renvoyés au navigateur.
- Change `admin123` dès la première connexion, et définis `SODEXAM_SECRET`.

## En local (Windows)
Double-clique sur `lancer_sodexam.bat` (place-le dans le même dossier que
`serveur.py`), puis ouvre l'adresse affichée.
