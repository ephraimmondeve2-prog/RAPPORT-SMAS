#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serveur central SODEXAM.

Roles
-----
- Sert l'application (le fichier HTML) a toutes les stations.
- Stocke les fichiers source (.ods METAR/SYNOP) charges par l'administrateur.
- Stocke les COMPTES (admin / stations) cote serveur -> partages par tous
  les postes. C'est la nouveaute : les identifiants crees par l'admin sont
  desormais valables depuis n'importe quel navigateur / ordinateur.

Lancement local
---------------
    pip install -r requirements.txt
    python serveur.py
puis, depuis chaque poste du reseau :  http://ADRESSE_DU_SERVEUR:5000/

Variables d'environnement (optionnelles)
----------------------------------------
    SODEXAM_ADMIN_KEY   cle d'ecriture pour le suivi (defaut : "sodexam-admin")
                        -> doit etre identique a SUIVI_ADMIN_KEY dans le HTML.
    SODEXAM_SECRET      cle secrete de signature des jetons de session.
                        Definissez-en une valeur stable (sinon les sessions
                        sont invalidees a chaque redemarrage).
    SODEXAM_ACCOUNTS    comptes a (re)creer automatiquement au demarrage, au
                        format JSON. INDISPENSABLE sur Render (hebergement
                        gratuit) car le disque y est ephemere : la base est
                        effacee a chaque redeploiement / mise en veille.
                        En definissant cette variable, vos comptes sont
                        recrees a chaque demarrage et restent donc permanents.
                        Exemple :
                        [{"username":"admin","password":"MonMotDePasse","role":"admin","station":"Administration"},
                         {"username":"abidjan","password":"abj2024","role":"station","station":"Abidjan"},
                         {"username":"bouake","password":"bke2024","role":"station","station":"Bouake"}]
    SODEXAM_HTML        nom du fichier HTML a servir (defaut : app.html)
    SODEXAM_PORT        port d'ecoute (defaut : 5000 ; Render fournit PORT)
    SODEXAM_DB          chemin de la base SQLite (defaut : data/suivi.db)
"""

import os
import json
import hmac
import hashlib
import sqlite3
import datetime
from flask import Flask, request, jsonify, send_from_directory, abort

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.environ.get("SODEXAM_HTML", "app.html")
ADMIN_KEY = os.environ.get("SODEXAM_ADMIN_KEY", "sodexam-admin")
SECRET    = os.environ.get("SODEXAM_SECRET", "sodexam-" + ADMIN_KEY)
DB_PATH   = os.environ.get("SODEXAM_DB", os.path.join(BASE_DIR, "data", "suivi.db"))
# Render fournit la variable PORT ; sinon SODEXAM_PORT ; sinon 5000.
PORT      = int(os.environ.get("PORT", os.environ.get("SODEXAM_PORT", "5000")))

MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32 Mo

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# --------------------------------------------------------------------------- #
#  Base de donnees
# --------------------------------------------------------------------------- #
def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = db()
    con.execute(
        """CREATE TABLE IF NOT EXISTS suivi (
               id         INTEGER PRIMARY KEY CHECK (id = 1),
               metar      TEXT,
               synop      TEXT,
               updated_at TEXT
           )"""
    )
    con.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
               username   TEXT PRIMARY KEY,
               role       TEXT NOT NULL,
               station    TEXT,
               salt       TEXT NOT NULL,
               hash       TEXT NOT NULL,
               created_at TEXT
           )"""
    )
    con.commit()
    con.close()


# ----- Suivi (inchange) ----------------------------------------------------- #
def read_suivi():
    con = db()
    row = con.execute(
        "SELECT metar, synop, updated_at FROM suivi WHERE id = 1"
    ).fetchone()
    con.close()
    if not row:
        return {"metar": None, "synop": None, "updatedAt": None}
    return {"metar": row[0], "synop": row[1], "updatedAt": row[2]}


def write_suivi(metar, synop):
    now = datetime.datetime.now().isoformat(timespec="seconds")
    con = db()
    con.execute(
        """INSERT INTO suivi (id, metar, synop, updated_at)
               VALUES (1, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
               metar = excluded.metar,
               synop = excluded.synop,
               updated_at = excluded.updated_at""",
        (metar, synop, now),
    )
    con.commit()
    con.close()
    return now


# ----- Comptes : hachage, jetons, CRUD -------------------------------------- #
def hash_pwd(salt, pwd):
    return hashlib.pbkdf2_hmac(
        "sha256", pwd.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


def new_salt():
    return os.urandom(16).hex()


def make_token(username):
    sig = hmac.new(SECRET.encode("utf-8"), username.encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return username + "." + sig


def user_from_token(token):
    """Renvoie la ligne du compte si le jeton est valide, sinon None."""
    if not token or "." not in token:
        return None
    username, sig = token.rsplit(".", 1)
    expected = hmac.new(SECRET.encode("utf-8"), username.encode("utf-8"),
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    con = db()
    row = con.execute(
        "SELECT username, role, station FROM accounts WHERE username = ?",
        (username,),
    ).fetchone()
    con.close()
    return dict(row) if row else None


def upsert_account(username, role, station, password, overwrite=True):
    con = db()
    exists = con.execute(
        "SELECT 1 FROM accounts WHERE username = ?", (username,)
    ).fetchone()
    if exists and not overwrite:
        con.close()
        return False
    salt = new_salt()
    con.execute(
        """INSERT INTO accounts (username, role, station, salt, hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(username) DO UPDATE SET
               role = excluded.role,
               station = excluded.station,
               salt = excluded.salt,
               hash = excluded.hash""",
        (username, role, station or username, salt, hash_pwd(salt, password),
         datetime.datetime.now().isoformat(timespec="seconds")),
    )
    con.commit()
    con.close()
    return True


def list_accounts():
    con = db()
    rows = con.execute(
        "SELECT username, role, station, created_at FROM accounts ORDER BY created_at"
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def count_admins():
    con = db()
    n = con.execute("SELECT COUNT(*) FROM accounts WHERE role = 'admin'").fetchone()[0]
    con.close()
    return n


def seed_accounts():
    """
    Recree les comptes au demarrage :
      1) a partir de la variable SODEXAM_ACCOUNTS (permanents, survit aux
         redemarrages de Render) ;
      2) garantit au moins un admin (admin/admin123) sinon.
    """
    raw = os.environ.get("SODEXAM_ACCOUNTS", "").strip()
    if raw:
        try:
            for a in json.loads(raw):
                if a.get("username") and a.get("password"):
                    upsert_account(
                        a["username"].strip(),
                        a.get("role", "station"),
                        a.get("station", ""),
                        a["password"],
                        overwrite=True,
                    )
        except Exception as e:  # pragma: no cover
            print("ATTENTION : SODEXAM_ACCOUNTS illisible (%s)" % e)

    if count_admins() == 0:
        upsert_account("admin", "admin", "Administration", "admin123",
                       overwrite=False)
        print("Compte admin par defaut cree : admin / admin123 "
              "(a changer rapidement).")


# --------------------------------------------------------------------------- #
#  CORS
# --------------------------------------------------------------------------- #
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = \
        "Content-Type, X-Admin-Key, X-Auth-Token"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    return resp


def require_admin():
    """Renvoie le compte admin courant ou interrompt avec 401/403."""
    user = user_from_token(request.headers.get("X-Auth-Token", ""))
    if not user:
        abort(401, description="Session invalide ou expiree, reconnectez-vous.")
    if user["role"] != "admin":
        abort(403, description="Action reservee a l'administrateur.")
    return user


# --------------------------------------------------------------------------- #
#  Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return send_from_directory(BASE_DIR, HTML_FILE)


# ----- Suivi transmissions -------------------------------------------------- #
@app.route("/api/suivi", methods=["GET", "POST", "OPTIONS"])
def api_suivi():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.method == "GET":
        return jsonify(read_suivi())
    if request.headers.get("X-Admin-Key", "") != ADMIN_KEY:
        abort(403, description="Cle administrateur invalide.")
    data = request.get_json(silent=True) or {}
    metar, synop = data.get("metar"), data.get("synop")
    if not metar and not synop:
        abort(400, description="Aucune donnee fournie (metar/synop).")
    return jsonify({"ok": True, "updatedAt": write_suivi(metar, synop)})


# ----- Authentification ----------------------------------------------------- #
@app.route("/api/login", methods=["POST", "OPTIONS"])
def api_login():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    con = db()
    row = con.execute(
        "SELECT * FROM accounts WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    con.close()
    if not row or row["hash"] != hash_pwd(row["salt"], password):
        abort(401, description="Identifiant ou mot de passe incorrect.")
    return jsonify({
        "ok": True,
        "token": make_token(row["username"]),
        "user": {"username": row["username"], "role": row["role"],
                 "station": row["station"]},
    })


@app.route("/api/me", methods=["GET", "OPTIONS"])
def api_me():
    if request.method == "OPTIONS":
        return ("", 204)
    user = user_from_token(request.headers.get("X-Auth-Token", ""))
    if not user:
        abort(401, description="Session invalide.")
    return jsonify({"ok": True, "user": user})


# ----- Gestion des comptes (admin) ------------------------------------------ #
@app.route("/api/accounts", methods=["GET", "POST", "OPTIONS"])
def api_accounts():
    if request.method == "OPTIONS":
        return ("", 204)
    require_admin()
    if request.method == "GET":
        return jsonify({"ok": True, "accounts": list_accounts()})
    # POST -> creation
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    role = data.get("role", "station")
    station = (data.get("station") or "").strip()
    if not username or not password:
        abort(400, description="Identifiant et mot de passe obligatoires.")
    con = db()
    exists = con.execute(
        "SELECT 1 FROM accounts WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    con.close()
    if exists:
        abort(409, description="Cet identifiant existe deja.")
    upsert_account(username, role, station, password, overwrite=True)
    return jsonify({"ok": True})


@app.route("/api/accounts/<username>", methods=["DELETE", "OPTIONS"])
def api_delete_account(username):
    if request.method == "OPTIONS":
        return ("", 204)
    me = require_admin()
    if username.lower() == me["username"].lower():
        abort(400, description="Vous ne pouvez pas supprimer votre propre compte.")
    con = db()
    row = con.execute(
        "SELECT role FROM accounts WHERE username = ? COLLATE NOCASE", (username,)
    ).fetchone()
    if not row:
        con.close()
        abort(404, description="Compte introuvable.")
    if row["role"] == "admin" and count_admins() <= 1:
        con.close()
        abort(400, description="Impossible de supprimer le dernier administrateur.")
    con.execute("DELETE FROM accounts WHERE username = ? COLLATE NOCASE", (username,))
    con.commit()
    con.close()
    return jsonify({"ok": True})


@app.route("/api/password", methods=["POST", "OPTIONS"])
def api_password():
    """Changement de son propre mot de passe."""
    if request.method == "OPTIONS":
        return ("", 204)
    user = user_from_token(request.headers.get("X-Auth-Token", ""))
    if not user:
        abort(401, description="Session invalide.")
    data = request.get_json(silent=True) or {}
    old, new = data.get("old") or "", data.get("new") or ""
    if not new:
        abort(400, description="Saisissez un nouveau mot de passe.")
    con = db()
    row = con.execute(
        "SELECT * FROM accounts WHERE username = ?", (user["username"],)
    ).fetchone()
    con.close()
    if not row or row["hash"] != hash_pwd(row["salt"], old):
        abort(403, description="Mot de passe actuel incorrect.")
    upsert_account(row["username"], row["role"], row["station"], new, overwrite=True)
    return jsonify({"ok": True})


@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(409)
@app.errorhandler(413)
def _err(e):
    return jsonify({"ok": False, "error": getattr(e, "description", str(e))}), e.code


# --------------------------------------------------------------------------- #
init_db()
seed_accounts()

if __name__ == "__main__":
    print("=" * 64)
    print(" Serveur SODEXAM")
    print(" Application :  http://0.0.0.0:%d/" % PORT)
    print(" Base        :  %s" % DB_PATH)
    print(" Comptes     :  %d (dont %d admin)" % (len(list_accounts()), count_admins()))
    print("=" * 64)
    app.run(host="0.0.0.0", port=PORT, debug=False)
