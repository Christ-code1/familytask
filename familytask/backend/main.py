import hashlib
import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, Query  # Importe les outils FastAPI pour les routes, les dépendances et la validation.
from fastapi.middleware.cors import CORSMiddleware  # Importe le middleware CORS pour autoriser les appels du frontend.
from sqlmodel import Field, Session, SQLModel, create_engine, select  # Importe SQLModel, les champs, le gestionnaire de session et la fonction de sélection.
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")  # Utilise la base fournie par l'environnement, avec SQLite en repli local.
engine_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_kwargs)  # Crée le moteur SQLAlchemy qui permet de communiquer avec la base.


def hash_password(pw: str) -> str:  # Transforme un mot de passe en hash SHA-256.
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()  # Encode le mot de passe et renvoie son empreinte hexadécimale.


class Task(SQLModel, table=True):  # Définit le modèle SQLModel pour une tâche enregistrée en base.
    id: int | None = Field(default=None, primary_key=True)  # Définit l'identifiant unique, auto-généré par la base.
    title: str = Field(nullable=False)  # Définit le titre de la tâche, obligatoire.
    done: bool = Field(default=False)  # Définit l'état de la tâche, faux par défaut.
    deadline: str | None = Field(default=None)  # Définit l'heure limite facultative au format HH:MM.


class Member(SQLModel, table=True):  # Définit le modèle SQLModel pour un membre de la famille.
    id: int | None = Field(default=None, primary_key=True)  # Définit l'identifiant unique, auto-généré par la base.
    email: str = Field(unique=True, index=True)  # Définit l'adresse email unique et indexée du membre.
    name: str  # Définit le nom du membre.
    lien: str  # Définit le lien familial du membre.
    is_admin: bool = Field(default=False)  # Définit les droits d'administration, désactivés par défaut.
    family_code: str = Field(index=True)  # Définit le code de famille indexé auquel le membre appartient.
    password_hash: str  # Stocke le hash du mot de passe plutôt que le mot de passe en clair.
    token: str | None = Field(default=None)  # Stocke le token d'authentification, effaçable lors de la déconnexion.


def get_session():  # Fournit une session de base de données aux routes qui en ont besoin.
    with Session(engine) as session:  # Ouvre une session puis la ferme automatiquement après la requête.
        yield session  # Rend la session disponible via l'injection de dépendance FastAPI.


def public_member(member: Member) -> dict:  # Prépare les informations publiques d'un membre sans son hash.
    return {  # Retourne uniquement les champs qui peuvent être renvoyés au frontend.
        "id": member.id,
        "email": member.email,
        "name": member.name,
        "lien": member.lien,
        "is_admin": member.is_admin,
        "family_code": member.family_code,
    }


def current_member(
    authorization: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Member:  # Identifie le membre connecté à partir de son token Bearer.
    scheme, _, token = (authorization or "").partition(" ")  # Sépare le schéma d'authentification et le token.
    token = token.strip() if scheme.lower() == "bearer" else ""  # N'accepte que l'en-tête Authorization au format Bearer.
    member = session.exec(select(Member).where(Member.token == token)).first() if token else None  # Recherche le membre correspondant.
    if not member:  # Refuse les tokens absents, invalides ou déjà supprimés.
        raise HTTPException(status_code=401, detail="Non connecté")  # Renvoie une erreur d'authentification neutre.
    return member  # Rend le membre authentifié disponible à la route.


app = FastAPI(title="FamilyTask")  # Crée l'application FastAPI principale avec le nom du projet.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # Autorise les requêtes du frontend depuis n'importe quelle origine.


@app.on_event("startup")  # Exécute cette fonction au démarrage de l'application.
def create_db_and_tables():  # Crée les tables de la base si elles n'existent pas.
    SQLModel.metadata.create_all(engine)  # Génère toutes les tables définies par les modèles SQLModel.
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as connection:
            columns = connection.execute(text("PRAGMA table_info(task)")).all()
            if not any(column[1] == "deadline" for column in columns):
                connection.execute(text("ALTER TABLE task ADD COLUMN deadline VARCHAR"))


@app.get("/api/health")  # Définit une route GET pour vérifier que l'API fonctionne.
def health():  # Fonction appelée quand on appelle /api/health.
    return {"status": "ok"}  # Retourne un JSON simple indiquant que le service est en vie.


@app.post("/api/signup")  # Définit la route de création du premier membre d'une famille.
def signup(
    email: str,
    password: str,
    name: str,
    family: str,
    lien: str = "parent",
    session: Session = Depends(get_session),
):  # Reçoit les informations du premier membre et le nom choisi pour sa famille.
    normalized_email = email.strip().lower()  # Normalise l'email pour éviter les doublons liés à la casse.
    if session.exec(select(Member).where(Member.email == normalized_email)).first():  # Vérifie que l'email est disponible.
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")  # Signale qu'un compte existe déjà.

    family_code = "fam-" + secrets.token_hex(4)  # Génère un identifiant unique pour la nouvelle famille.
    member = Member(  # Construit le premier membre avec les droits administrateur.
        email=normalized_email,
        password_hash=hash_password(password),
        name=name,
        lien=lien,
        is_admin=True,
        family_code=family_code,
        token=secrets.token_hex(16),
    )
    session.add(member)  # Ajoute le membre à la session de base de données.
    session.commit()  # Enregistre le compte et son token.
    session.refresh(member)  # Recharge l'identifiant généré par la base.
    return {"token": member.token, **public_member(member)}  # Renvoie le token et les informations publiques.


@app.post("/api/login")  # Définit la route de connexion d'un membre existant.
def login(email: str, password: str, session: Session = Depends(get_session)):  # Vérifie les identifiants et crée une nouvelle session.
    normalized_email = email.strip().lower()  # Utilise la même normalisation que lors de l'inscription.
    member = session.exec(select(Member).where(Member.email == normalized_email)).first()  # Recherche le compte par email.
    if not member or member.password_hash != hash_password(password):  # Compare le hash sans révéler la cause de l'échec.
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect")  # Renvoie un message d'erreur neutre.

    member.token = secrets.token_hex(16)  # Remplace l'ancien token par un nouveau token de session.
    session.add(member)  # Marque la modification pour sauvegarde.
    session.commit()  # Enregistre le nouveau token.
    return {"token": member.token, **public_member(member)}  # Renvoie le token et les informations publiques.


@app.get("/api/me")  # Définit la route qui renvoie le membre actuellement connecté.
def me(member: Member = Depends(current_member)):  # Reçoit le membre identifié par son token Bearer.
    return public_member(member)  # Exclut le hash du mot de passe et le token de la réponse.


@app.post("/api/logout")  # Définit la route de déconnexion du membre connecté.
def logout(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Invalide le token utilisé pour cette requête.
    member.token = None  # Efface le token en base afin qu'il ne puisse plus être réutilisé.
    session.add(member)  # Marque le membre comme modifié.
    session.commit()  # Enregistre l'invalidation du token.
    return {"ok": True, "message": "Déconnexion réussie"}  # Confirme la déconnexion.


@app.get("/api/tasks")  # Définit une route GET pour récupérer toutes les tâches.
def get_tasks():  # Fonction appelée pour lire toutes les tâches enregistrées.
    with Session(engine) as session:  # Ouvre une session SQLModel pour dialoguer avec la base.
        tasks = session.exec(select(Task)).all()  # Sélectionne toutes les lignes de la table Task.
        return tasks  # Renvoie la liste des tâches sous forme de JSON au frontend.


@app.post("/api/tasks")  # Définit une route POST pour créer une nouvelle tâche.
def create_task(
    title: str = Query(..., min_length=1, description="Titre de la tâche, obligatoire et non vide."),
    deadline: str | None = Query(default=None, description="Heure limite facultative au format HH:MM."),
):  # Reçoit le titre et l'heure limite facultative de la tâche.
    if not title or not title.strip():  # Vérifie qu'il y a bien un titre significatif après suppression des espaces.
        raise HTTPException(status_code=422, detail="Title cannot be empty")  # Refuse proprement une tâche sans nom avec une erreur 422.

    with Session(engine) as session:  # Ouvre une session SQLModel pour écrire dans la base.
        db_task = Task(title=title.strip(), done=False, deadline=deadline)  # Crée une nouvelle tâche avec ses données nettoyées.
        session.add(db_task)  # Ajoute la tâche à la session avant l'enregistrement.
        session.commit()  # Enregistre la tâche dans la base de données.
        session.refresh(db_task)  # Recharge l'objet pour obtenir l'id généré automatiquement.
        return db_task  # Renvoie la tâche créée avec son id au frontend.


@app.patch("/api/tasks/{task_id}")  # Définit une route PATCH pour modifier une tâche existante.
def update_task(task_id: int):  # Fonction appelée pour inverser le statut done d'une tâche.
    with Session(engine) as session:  # Ouvre une session SQLModel pour modifier la base.
        db_task = session.get(Task, task_id)  # Cherche la tâche correspondant à l'id donné.
        if not db_task:  # Si aucune tâche ne correspond, on renvoie une erreur 404.
            raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")  # Signale clairement que la tâche n'existe pas.
        db_task.done = not db_task.done  # Inverse la valeur booléenne : True devient False, False devient True.
        session.add(db_task)  # Marque la tâche modifiée pour sauvegarde.
        session.commit()  # Enregistre le changement dans la base.
        session.refresh(db_task)  # Recharge l'objet pour obtenir le dernier état enregistré.
        return db_task  # Renvoie la tâche avec le nouveau statut done au frontend.


@app.delete("/api/tasks/{task_id}")  # Définit une route DELETE pour supprimer une tâche.
def delete_task(task_id: int):  # Fonction appelée pour supprimer une tâche par son identifiant.
    with Session(engine) as session:  # Ouvre une session SQLModel pour faire la suppression.
        db_task = session.get(Task, task_id)  # Recherche la tâche à supprimer par son id.
        if not db_task:  # Si la tâche n'existe pas, on renvoie une erreur 404.
            raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")  # Signale clairement que la tâche n'existe pas.
        session.delete(db_task)  # Supprime l'objet de la base de données.
        session.commit()  # Confirme la suppression dans la base.
        return {"ok": True, "message": "Task deleted"}  # Renvoie une confirmation de suppression au frontend.
