import os
# Base SQLite de test, neuve à chaque exécution.
if os.path.exists("./test.db"):
    os.remove("./test.db")
os.environ["DATABASE_URL"] = "sqlite:///./test.db"  # Force la base de test (écrase la valeur Postgres définie par docker-compose).
os.environ.pop("AI_TOKEN", None)  # Sans clé, l'assistant ne doit jamais essayer d'appeler l'IA.

from fastapi.testclient import TestClient
from main import app
import main


def creer_famille(client, email="chef@fam.fr", password="secret", name="Chef", family="Test"):
    """Inscrit un premier membre (admin) et renvoie ses en-têtes d'authentification."""
    r = client.post("/api/signup", params={
        "email": email, "password": password, "name": name, "family": family})
    assert r.status_code == 200
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}, r.json()


def test_inscription_puis_tache():
    # Le "with" démarre l'app (crée les tables).
    with TestClient(app) as client:
        # 1) On crée une famille de test → on récupère un token
        headers, _ = creer_famille(client, email="test1@fam.fr")

        # 2) On crée une tâche pour soi
        r = client.post("/api/tasks", params={"title": "Sortir les poubelles"}, headers=headers)
        assert r.status_code == 200

        # 3) On relit ses tâches : elle est là
        r = client.get("/api/tasks", headers=headers)
        assert r.status_code == 200
        assert any(t["title"] == "Sortir les poubelles" for t in r.json())


def test_sans_token_refuse():
    with TestClient(app) as client:
        assert client.get("/api/tasks").status_code == 401


def test_email_deja_utilise_refuse():
    with TestClient(app) as client:
        creer_famille(client, email="test2@fam.fr")
        r = client.post("/api/signup", params={
            "email": "test2@fam.fr", "password": "autre", "name": "Doublon", "family": "Autre"})
        assert r.status_code == 400


def test_mauvais_mot_de_passe_refuse():
    with TestClient(app) as client:
        creer_famille(client, email="test3@fam.fr", password="bonmotdepasse")
        r = client.post("/api/login", params={"email": "test3@fam.fr", "password": "mauvais"})
        assert r.status_code == 401


def test_logout_invalide_le_jeton():
    """Après déconnexion, l'ancien jeton ne doit plus ouvrir aucune porte."""
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="test4@fam.fr")

        # Le jeton marche
        assert client.get("/api/me", headers=headers).status_code == 200

        # On se déconnecte
        assert client.post("/api/logout", headers=headers).status_code == 200

        # Le MEME jeton ne vaut plus rien : le serveur l'a invalidé
        assert client.get("/api/me", headers=headers).status_code == 401
        assert client.get("/api/tasks", headers=headers).status_code == 401


def test_titre_de_tache_vide_refuse():
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="test5@fam.fr")
        r = client.post("/api/tasks", params={"title": "   "}, headers=headers)
        assert r.status_code == 422


def test_cocher_puis_supprimer_une_tache():
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="test6@fam.fr")
        tache = client.post("/api/tasks", params={"title": "Ranger"}, headers=headers).json()

        r = client.patch(f"/api/tasks/{tache['id']}", headers=headers)
        assert r.status_code == 200
        assert r.json()["done"] is True

        r = client.delete(f"/api/tasks/{tache['id']}", headers=headers)
        assert r.status_code == 200
        assert client.get("/api/tasks", headers=headers).json() == []


def test_membre_non_admin_ne_peut_pas_voir_la_famille():
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="admin7@fam.fr")
        client.post("/api/members", params={
            "email": "enfant7@fam.fr", "password": "secret", "name": "Léa", "lien": "fille",
        }, headers=headers)

        r = client.post("/api/login", params={"email": "enfant7@fam.fr", "password": "secret"})
        headers_enfant = {"Authorization": f"Bearer {r.json()['token']}"}

        assert client.get("/api/members", headers=headers_enfant).status_code == 403


def test_suppression_membre_supprime_aussi_ses_taches():
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="admin8@fam.fr")
        enfant = client.post("/api/members", params={
            "email": "enfant8@fam.fr", "password": "secret", "name": "Léa", "lien": "fille",
        }, headers=headers).json()
        client.post("/api/tasks", params={"title": "Devoirs", "member_id": enfant["id"]}, headers=headers)

        r = client.delete(f"/api/members/{enfant['id']}", headers=headers)
        assert r.status_code == 200
        assert client.get("/api/tasks/famille", headers=headers).json() == []


def test_assistant_sans_cle_ia_repond_poliment():
    """Sans AI_TOKEN configuré, l'assistant doit répondre proprement plutôt que planter."""
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="test9@fam.fr")
        r = client.post("/api/assistant", params={"message": "Ajoute la vaisselle pour Chef"}, headers=headers)
        assert r.status_code == 200
        assert "AI_TOKEN" in r.json()["reply"]


def test_assistant_ne_devine_pas_si_plusieurs_filles(monkeypatch):
    """Le cœur de la consigne du Jour 4 : si le message parle d'un lien (« ma fille »)
    et que plusieurs personnes partagent ce lien, l'assistant doit renvoyer une question
    de désambiguïsation — SANS jamais appeler l'IA — et ce contrôle doit se faire sur le
    message brut, avant tout appel au modèle."""
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="admin10@fam.fr")
        for prenom, email_local in (("Léa", "lea10"), ("Emma", "emma10")):
            client.post("/api/members", params={
                "email": f"{email_local}@fam.fr", "password": "secret", "name": prenom, "lien": "fille",
            }, headers=headers)

        # On donne une fausse clé pour prouver que même avec l'IA "disponible",
        # elle n'est jamais sollicitée quand le message est ambigu.
        monkeypatch.setenv("AI_TOKEN", "fausse-cle-de-test")

        def echoue_si_appelee(*args, **kwargs):
            raise AssertionError("L'IA ne doit pas être appelée quand le message est ambigu.")

        monkeypatch.setattr(main.httpx, "AsyncClient", echoue_si_appelee)

        r = client.post("/api/assistant", params={"message": "Ajoute la vaisselle pour ma fille"}, headers=headers)
        assert r.status_code == 200
        reponse = r.json()["reply"]
        assert "Léa" in reponse and "Emma" in reponse
        assert "?" in reponse


def test_assistant_un_seul_correspondant_au_lien_nest_pas_ambigu():
    """Un seul membre porte le lien cité : pas de question, l'assistant continue normalement."""
    with TestClient(app) as client:
        headers, _ = creer_famille(client, email="admin11@fam.fr")
        client.post("/api/members", params={
            "email": "lea11@fam.fr", "password": "secret", "name": "Léa", "lien": "fille",
        }, headers=headers)

        r = client.post("/api/assistant", params={"message": "Ajoute la vaisselle pour ma fille"}, headers=headers)
        assert r.status_code == 200
        # Sans AI_TOKEN, l'assistant explique juste qu'il n'est pas configuré :
        # il ne doit surtout pas avoir posé la question de désambiguïsation à tort.
        assert "plusieurs" not in r.json()["reply"].lower()
