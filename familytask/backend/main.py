from fastapi import FastAPI, HTTPException, Query  # Importe FastAPI, HTTPException et Query pour gérer les erreurs HTTP et la validation des paramètres.
from fastapi.middleware.cors import CORSMiddleware  # Importe le middleware CORS pour autoriser les appels du frontend.
from sqlmodel import Field, Session, SQLModel, create_engine, select  # Importe SQLModel, les champs, le gestionnaire de session et la fonction de sélection.

DATABASE_URL = "sqlite:///./tasks.db"  # Définit l'URL de la base SQLite dans le dossier backend.
engine = create_engine(DATABASE_URL)  # Crée le moteur SQLAlchemy qui permet de communiquer avec la base.


class Task(SQLModel, table=True):  # Définit le modèle SQLModel pour une tâche enregistrée en base.
    id: int | None = Field(default=None, primary_key=True)  # Définit l'identifiant unique, auto-généré par la base.
    title: str = Field(nullable=False)  # Définit le titre de la tâche, obligatoire.
    done: bool = Field(default=False)  # Définit l'état de la tâche, faux par défaut.


app = FastAPI(title="FamilyTask")  # Crée l'application FastAPI principale avec le nom du projet.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])  # Autorise les requêtes du frontend depuis n'importe quelle origine.


@app.on_event("startup")  # Exécute cette fonction au démarrage de l'application.
def create_db_and_tables():  # Crée les tables de la base si elles n'existent pas.
    SQLModel.metadata.create_all(engine)  # Génère toutes les tables définies par les modèles SQLModel.


@app.get("/api/health")  # Définit une route GET pour vérifier que l'API fonctionne.
def health():  # Fonction appelée quand on appelle /api/health.
    return {"status": "ok"}  # Retourne un JSON simple indiquant que le service est en vie.


@app.get("/api/tasks")  # Définit une route GET pour récupérer toutes les tâches.
def get_tasks():  # Fonction appelée pour lire toutes les tâches enregistrées.
    with Session(engine) as session:  # Ouvre une session SQLModel pour dialoguer avec la base.
        tasks = session.exec(select(Task)).all()  # Sélectionne toutes les lignes de la table Task.
        return tasks  # Renvoie la liste des tâches sous forme de JSON au frontend.


@app.post("/api/tasks")  # Définit une route POST pour créer une nouvelle tâche.
def create_task(title: str = Query(..., min_length=1, description="Titre de la tâche, obligatoire et non vide.")):  # Reçoit le titre et refuse les valeurs vides avec une validation FastAPI.
    if not title or not title.strip():  # Vérifie qu'il y a bien un titre significatif après suppression des espaces.
        raise HTTPException(status_code=422, detail="Title cannot be empty")  # Refuse proprement une tâche sans nom avec une erreur 422.

    with Session(engine) as session:  # Ouvre une session SQLModel pour écrire dans la base.
        db_task = Task(title=title.strip(), done=False)  # Crée une nouvelle tâche avec un titre nettoyé et done à False.
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
