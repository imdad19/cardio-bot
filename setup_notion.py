"""
setup_notion.py -- Run ONCE to create the Notion database with correct schema
Includes both HDJ and Bloc fields for cardiology patient management.
Usage: python setup_notion.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

from notion_client import Client

NOTION_API_KEY = os.environ["NOTION_API_KEY"]
NOTION_PAGE_ID = os.environ["NOTION_PAGE_ID"]

notion = Client(auth=NOTION_API_KEY)


def create_patient_database():
    db = notion.databases.create(
        parent={"type": "page_id", "page_id": NOTION_PAGE_ID},
        title=[{"type": "text", "text": {"content": "Patients - Cardiologie"}}],
        properties={
            "Nom complet":          {"title": {}},
            "Prenom":               {"rich_text": {}},
            "Age":                  {"number": {"format": "number"}},
            "Sexe":                 {"select": {"options": [
                                        {"name": "Homme", "color": "blue"},
                                        {"name": "Femme", "color": "pink"},
                                        {"name": "Non precise", "color": "gray"},
                                    ]}},
            "N Dossier":            {"rich_text": {}},
            "Adresse":              {"rich_text": {}},
            "Clinique":             {"rich_text": {}},
            "Diagnostic final":     {"rich_text": {}},
            "Examen":               {"select": {"options": [
                                        {"name": "ETT", "color": "blue"},
                                        {"name": "ETO", "color": "purple"},
                                        {"name": "ECG", "color": "green"},
                                        {"name": "Holter", "color": "yellow"},
                                        {"name": "Epreuve d'effort", "color": "orange"},
                                    ]}},
            "Tension arterielle":   {"rich_text": {}},
            "Frequence cardiaque":  {"number": {"format": "number"}},
            "Antecedents":          {"rich_text": {}},
            "Traitement en cours":  {"rich_text": {}},
            "Decision finale":      {"rich_text": {}},
            "Evolution":            {"rich_text": {}},
            "Date de visite":       {"date": {}},
            "Notes":                {"rich_text": {}},
            "Statut":               {"select": {"options": [
                                        {"name": "Actif",   "color": "green"},
                                        {"name": "Suivi",   "color": "yellow"},
                                        {"name": "Archive", "color": "gray"},
                                    ]}},
        }
    )
    print("Database created!")
    print(f"Database ID: {db['id']}")
    print()
    print("Add this to your .env file:")
    print(f"NOTION_DATABASE_ID={db['id']}")
    return db["id"]


if __name__ == "__main__":
    create_patient_database()
