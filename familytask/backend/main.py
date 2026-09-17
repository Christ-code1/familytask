import json
import hashlib
import os
import secrets
import unicodedata

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query  # Importe les outils FastAPI pour les routes, les dépendances et la validation.
from fastapi.middleware.cors import CORSMiddleware  # Importe le middleware CORS pour autoriser les appels du frontend.
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer  # Déclare l'authentification Bearer pour OpenAPI et Swagger.
from sqlmodel import Field, Session, SQLModel, create_engine, select  # Importe SQLModel, les champs, le gestionnaire de session et la fonction de sélection.
from sqlalchemy import text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tasks.db")  # Utilise la base fournie par l'environnement, avec SQLite en repli local.
engine_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_kwargs)  # Crée le moteur SQLAlchemy qui permet de communiquer avec la base.
bearer_scheme = HTTPBearer(auto_error=False)  # Permet à Swagger d'utiliser le bouton Authorize sans lever d'erreur automatiquement.
LIENS_DEFAUT = ["mère", "père", "fille", "fils", "frère", "sœur", "grand-mère", "grand-père", "oncle", "tante"]  # Liste initiale des liens de parenté.
TOOLS = [{
    "type": "function",
    "function": {
        "name": "ajouter_tache",
        "description": "Ajoute une tâche à la liste d'une personne de la famille.",
        "parameters": {
            "type": "object",
            "properties": {
                "titre": {"type": "string", "description": "Le titre de la tâche."},
                "personne": {"type": "string", "description": "Le nom ou le lien familial de la personne."},
            },
            "required": ["titre", "personne"],
            "additionalProperties": False,
        },
    },
}]


def hash_password(pw: str) -> str:  # Transforme un mot de passe en hash SHA-256.
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()  # Encode le mot de passe et renvoie son empreinte hexadécimale.


def normalize_name(text: str) -> str:  # Met un nom en forme simple pour comparer sans piéger sur la casse ou les accents.
    text = text.strip().lower()  # Retire les espaces superflus et uniformise la casse.
    decomposed = unicodedata.normalize("NFKD", text)  # Sépare chaque lettre accentuée de son accent.
    return "".join(char for char in decomposed if not unicodedata.combining(char))  # Ne garde que les lettres, sans les accents.


class Task(SQLModel, table=True):  # Définit le modèle SQLModel pour une tâche enregistrée en base.
    id: int | None = Field(default=None, primary_key=True)  # Définit l'identifiant unique, auto-généré par la base.
    title: str = Field(nullable=False)  # Définit le titre de la tâche, obligatoire.
    done: bool = Field(default=False)  # Définit l'état de la tâche, faux par défaut.
    deadline: str | None = Field(default=None)  # Définit l'heure limite facultative au format HH:MM.
    member_id: int | None = Field(default=None, foreign_key="member.id", index=True)  # Définit le membre auquel la tâche est assignée.


class Lien(SQLModel, table=True):  # Définit un lien de parenté propre à une famille.
    id: int | None = Field(default=None, primary_key=True)  # Définit l'identifiant unique du lien.
    family_code: str = Field(index=True)  # Associe le lien à une famille précise.
    label: str = Field(nullable=False)  # Stocke le libellé affiché du lien.


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


def find_member_by_name(members: list[Member], person: str) -> Member | None:  # Cherche un membre de la famille par son prénom.
    target = normalize_name(person)  # Normalise le nom fourni par l'assistant IA.
    return next((m for m in members if normalize_name(m.name) == target), None)  # Renvoie le premier membre dont le nom correspond.


POSSESSIFS = ("ma ", "mon ", "mes ", "notre ", "nos ", "la ", "le ", "les ", "l'")  # Articles à retirer avant de comparer un lien.


def strip_possessive(phrase: str) -> str:  # Retire l'article possessif d'une expression comme « ma fille ».
    normalized = phrase.strip().lower()  # Uniformise la casse avant de chercher un préfixe.
    for prefix in POSSESSIFS:  # Essaie chaque article possible dans l'ordre.
        if normalized.startswith(prefix):  # Coupe le préfixe s'il est présent.
            return normalized[len(prefix):].strip()
    return normalized  # Renvoie l'expression telle quelle si aucun article n'a été trouvé.


def find_members_by_lien(members: list[Member], phrase: str) -> list[Member]:  # Cherche les membres partageant un lien de parenté.
    target = normalize_name(strip_possessive(phrase))  # Isole le lien (« fille ») et le normalise.
    return [m for m in members if normalize_name(m.lien) == target]  # Renvoie tous les membres portant ce lien.


def public_member(member: Member) -> dict:  # Prépare les informations publiques d'un membre sans son hash.
    return {  # Retourne uniquement les champs qui peuvent être renvoyés au frontend.
        "id": member.id,
        "email": member.email,
        "name": member.name,
        "lien": member.lien,
        "is_admin": member.is_admin,
        "family_code": member.family_code,
    }


def require_admin(member: Member) -> Member:  # Vérifie que le compte connecté possède les droits d'administration.
    if not member.is_admin:  # Refuse les comptes qui ne peuvent pas gérer la famille.
        raise HTTPException(status_code=403, detail="Seul l'admin peut gérer la famille")
    return member  # Rend l'admin validé disponible à la route.


def current_member(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> Member:  # Identifie le membre connecté à partir de son token Bearer.
    token = credentials.credentials if credentials else ""  # Récupère le token Bearer fourni par l'en-tête Authorization.
    member = session.exec(select(Member).where(Member.token == token)).first() if token else None  # Recherche le membre correspondant.
    if not member:  # Refuse les tokens absents, invalides ou déjà supprimés.
        raise HTTPException(status_code=401, detail="Non connecté")  # Renvoie une erreur d'authentification neutre.
    return member  # Rend le membre authentifié disponible à la route.


app = FastAPI(title="FamilyTask")  # Crée l'application FastAPI principale avec le nom du projet.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # Autorise les requêtes du frontend depuis n'importe quelle origine.


@app.on_event("startup")  # Exécute cette fonction au démarrage de l'application.
def create_db_and_tables():  # Crée les tables de la base si elles n'existent pas.
    SQLModel.metadata.create_all(engine)  # Génère toutes les tables définies par les modèles SQLModel.
    with Session(engine) as session:
        family_codes = session.exec(select(Member.family_code).distinct()).all()
        for family_code in family_codes:
            if not session.exec(select(Lien).where(Lien.family_code == family_code)).first():
                session.add_all(Lien(family_code=family_code, label=default_label) for default_label in LIENS_DEFAUT)
        session.commit()
    if DATABASE_URL.startswith("sqlite"):
        with engine.begin() as connection:
            columns = connection.execute(text("PRAGMA table_info(task)")).all()
            if not any(column[1] == "deadline" for column in columns):
                connection.execute(text("ALTER TABLE task ADD COLUMN deadline VARCHAR"))
            if not any(column[1] == "member_id" for column in columns):
                connection.execute(text("ALTER TABLE task ADD COLUMN member_id INTEGER"))
    else:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS deadline VARCHAR"))
            connection.execute(text("ALTER TABLE task ADD COLUMN IF NOT EXISTS member_id INTEGER REFERENCES member(id)"))
            connection.execute(text("ALTER TABLE member ALTER COLUMN token DROP NOT NULL"))


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
    session.add_all(Lien(family_code=family_code, label=default_label) for default_label in LIENS_DEFAUT)  # Initialise les liens de la nouvelle famille.
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


@app.get("/api/members")  # Définit la route qui renvoie les membres de la famille connectée.
def get_members(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
) -> list[dict]:  # Renvoie uniquement les membres partageant la famille du compte connecté.
    require_admin(member)  # Réserve la liste des comptes à l'administrateur.
    members = session.exec(
        select(Member)
        .where(Member.family_code == member.family_code)
        .order_by(Member.id != member.id, Member.id)
    ).all()  # Inclut explicitement le membre connecté, placé en première position.
    return [public_member(family_member) for family_member in members]


@app.get("/api/liens")  # Définit la route qui renvoie les liens de parenté de la famille.
def get_liens(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Renvoie la liste des liens gérés par l'administrateur.
    require_admin(member)  # Réserve la gestion des liens à l'administrateur.
    liens = session.exec(select(Lien).where(Lien.family_code == member.family_code)).all()
    return [lien.label for lien in liens]


@app.post("/api/liens")  # Définit la route d'ajout d'un lien de parenté.
def create_lien(
    label: str = Query(..., min_length=1, description="Libellé du lien de parenté."),
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Ajoute un lien uniquement dans la famille de l'admin connecté.
    require_admin(member)  # Refuse toute modification par un non-admin.
    normalized_label = label.strip()  # Nettoie les espaces avant l'enregistrement.
    if not normalized_label:  # Refuse un libellé vide après nettoyage.
        raise HTTPException(status_code=422, detail="Le lien ne peut pas être vide")
    existing = session.exec(select(Lien).where(
        Lien.family_code == member.family_code, Lien.label == normalized_label
    )).first()
    if not existing:  # N'ajoute pas deux fois le même lien dans une famille.
        session.add(Lien(family_code=member.family_code, label=normalized_label))
        session.commit()
    return [lien.label for lien in session.exec(select(Lien).where(Lien.family_code == member.family_code)).all()]


@app.post("/api/members")  # Définit la route de création d'un compte familial.
def create_member(
    email: str,
    password: str,
    name: str,
    lien: str = "",
    is_admin: bool = False,
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Crée un compte dans la famille de l'administrateur connecté.
    require_admin(member)  # Réserve la création de comptes à l'administrateur.
    normalized_email = email.strip().lower()  # Normalise l'adresse avant de vérifier son unicité.
    if session.exec(select(Member).where(Member.email == normalized_email)).first():
        raise HTTPException(status_code=400, detail="Cet email est déjà utilisé")
    new_member = Member(
        email=normalized_email,
        password_hash=hash_password(password),
        name=name.strip(),
        lien=lien.strip(),
        is_admin=is_admin,
        family_code=member.family_code,
    )
    session.add(new_member)  # Ajoute le nouveau compte à la session.
    session.commit()  # Enregistre le compte dans la base.
    session.refresh(new_member)  # Recharge son identifiant généré.
    return public_member(new_member)


@app.delete("/api/members/{member_id}")  # Définit la route de suppression d'un compte familial.
def delete_member(
    member_id: int,
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Supprime un membre et toutes ses tâches dans la famille de l'admin.
    require_admin(member)  # Réserve la suppression de comptes à l'administrateur.
    member_to_delete = session.get(Member, member_id)
    if not member_to_delete or member_to_delete.family_code != member.family_code:
        raise HTTPException(status_code=404, detail="Membre introuvable dans votre famille")
    if member_to_delete.id == member.id:  # Empêche l'administrateur de supprimer son propre compte.
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas supprimer votre propre compte")
    tasks = session.exec(select(Task).where(Task.member_id == member_to_delete.id)).all()
    for task in tasks:  # Supprime d'abord les tâches pour respecter la clé étrangère.
        session.delete(task)
    session.delete(member_to_delete)  # Supprime ensuite le compte familial.
    session.commit()  # Valide la suppression des tâches et du membre.
    return {"ok": True, "message": "Membre supprimé"}


@app.post("/api/logout")  # Définit la route de déconnexion du membre connecté.
def logout(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Invalide le token utilisé pour cette requête.
    member.token = None  # Efface le token en base afin qu'il ne puisse plus être réutilisé.
    session.add(member)  # Marque le membre comme modifié.
    session.commit()  # Enregistre l'invalidation du token.
    return {"ok": True, "message": "Déconnexion réussie"}  # Confirme la déconnexion.


@app.get("/api/tasks")  # Définit une route GET pour récupérer les tâches du membre connecté.
def get_tasks(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Fonction appelée pour lire les tâches assignées au membre connecté.
    return session.exec(select(Task).where(Task.member_id == member.id)).all()  # Ne renvoie que les tâches qui lui sont assignées.


@app.get("/api/tasks/famille")  # Définit une route GET pour récupérer toutes les tâches de la famille.
def get_family_tasks(
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Fonction appelée pour lire les tâches de la famille de l'admin connecté.
    if not member.is_admin:  # Réserve cette vue globale à l'administrateur de la famille.
        raise HTTPException(status_code=403, detail="Seul l'admin peut voir les tâches de la famille")
    return session.exec(
        select(Task).join(Member, Task.member_id == Member.id).where(Member.family_code == member.family_code)
    ).all()  # Filtre les tâches par la famille portée par le compte connecté.


@app.post("/api/assistant")  # Définit une route POST pour interroger l'assistant IA.
async def assistant(
    message: str,
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Envoie le message du membre connecté à GitHub Models.
    ai_token = os.getenv("AI_TOKEN", "").strip()
    if not ai_token:
        return {"reply": "L'assistant IA n'est pas configuré : la clé AI_TOKEN est manquante."}

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://models.github.ai/inference/chat/completions",
                headers={"Authorization": f"Bearer {ai_token}"},
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": message}],
                    "tools": TOOLS,
                },
            )
            response.raise_for_status()
            data = response.json()
            assistant_message = data["choices"][0]["message"]
            tool_calls = assistant_message.get("tool_calls") or []
            if not tool_calls:
                return {"reply": assistant_message.get("content", "")}

            tool_call = tool_calls[0]
            function = tool_call.get("function", {})
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if function.get("name") != "ajouter_tache":
                return {"reply": "L'assistant a demandé une action inconnue."}

            title = str(arguments.get("titre", "")).strip()
            person = str(arguments.get("personne", "")).strip()
            if not title or not person:
                return {"reply": "Le titre et la personne sont nécessaires pour ajouter une tâche."}

            family_members = session.exec(
                select(Member).where(Member.family_code == member.family_code)
            ).all()
            assignee = find_member_by_name(family_members, person)
            if not assignee:
                lien_matches = find_members_by_lien(family_members, person)  # Essaie ensuite par lien de parenté (« ma fille »).
                if len(lien_matches) > 1:  # Plusieurs personnes partagent ce lien : on demande de préciser.
                    noms = ", ".join(m.name for m in lien_matches)
                    return {"reply": f"Il y a plusieurs correspondances pour « {person} » : {noms}. Pour qui exactement ?"}
                if len(lien_matches) == 1:  # Un seul membre correspond : pas d'ambiguïté.
                    assignee = lien_matches[0]
                else:
                    return {"reply": f"Je ne trouve pas de membre correspondant à « {person} »."}

            session.add(Task(title=title, member_id=assignee.id))
            session.commit()
            return {"reply": f'Tâche ajoutée pour {assignee.name} : « {title} ». '}
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        return {"reply": "L'assistant IA n'a pas pu répondre. Vérifie ta connexion et réessaie."}


@app.post("/api/tasks")  # Définit une route POST pour créer une nouvelle tâche.
def create_task(
    title: str = Query(..., min_length=1, description="Titre de la tâche, obligatoire et non vide."),
    deadline: str | None = Query(default=None, description="Heure limite facultative au format HH:MM."),
    member_id: int | None = Query(default=None, description="Membre destinataire, réservé à l'admin."),
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Reçoit le titre et l'heure limite facultative de la tâche.
    if not title or not title.strip():  # Vérifie qu'il y a bien un titre significatif après suppression des espaces.
        raise HTTPException(status_code=422, detail="Title cannot be empty")  # Refuse proprement une tâche sans nom avec une erreur 422.

    assignee_id = member.id  # Par défaut, une tâche est toujours assignée au compte connecté.
    if member_id is not None and member.is_admin:  # Un admin peut choisir un autre destinataire.
        assignee = session.get(Member, member_id)
        if not assignee or assignee.family_code != member.family_code:
            raise HTTPException(status_code=404, detail="Membre introuvable dans votre famille")
        assignee_id = assignee.id

    db_task = Task(title=title.strip(), done=False, deadline=deadline, member_id=assignee_id)  # Crée la tâche pour le membre retenu.
    session.add(db_task)  # Ajoute la tâche à la session avant l'enregistrement.
    session.commit()  # Enregistre la tâche dans la base de données.
    session.refresh(db_task)  # Recharge l'objet pour obtenir l'id généré automatiquement.
    return db_task  # Renvoie la tâche créée avec son id au frontend.


@app.patch("/api/tasks/{task_id}")  # Définit une route PATCH pour modifier une tâche existante.
def update_task(
    task_id: int,
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Fonction appelée pour inverser le statut done d'une tâche de la famille.
    db_task = session.get(Task, task_id)  # Cherche la tâche correspondant à l'id donné.
    assignee = session.get(Member, db_task.member_id) if db_task and db_task.member_id else None
    if not db_task or not assignee or assignee.family_code != member.family_code:  # Vérifie que la tâche appartient à la famille.
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")  # Signale clairement que la tâche n'existe pas.
    db_task.done = not db_task.done  # Inverse la valeur booléenne : True devient False, False devient True.
    session.add(db_task)  # Marque la tâche modifiée pour sauvegarde.
    session.commit()  # Enregistre le changement dans la base.
    session.refresh(db_task)  # Recharge l'objet pour obtenir le dernier état enregistré.
    return db_task  # Renvoie la tâche avec le nouveau statut done au frontend.


@app.delete("/api/tasks/{task_id}")  # Définit une route DELETE pour supprimer une tâche.
def delete_task(
    task_id: int,
    member: Member = Depends(current_member),
    session: Session = Depends(get_session),
):  # Fonction appelée pour supprimer une tâche de la famille.
    db_task = session.get(Task, task_id)  # Recherche la tâche à supprimer par son id.
    assignee = session.get(Member, db_task.member_id) if db_task and db_task.member_id else None
    if not db_task or not assignee or assignee.family_code != member.family_code:  # Vérifie que la tâche appartient à la famille.
        raise HTTPException(status_code=404, detail=f"Task with id {task_id} not found")  # Signale clairement que la tâche n'existe pas.
    session.delete(db_task)  # Supprime l'objet de la base de données.
    session.commit()  # Confirme la suppression dans la base.
    return {"ok": True, "message": "Task deleted"}  # Renvoie une confirmation de suppression.
