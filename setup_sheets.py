"""
setup_sheets.py -- Run ONCE to create the Google Spreadsheet with HDJ and Bloc sheets.
Uses OAuth2 with your Google Client ID/Secret.
On first run, a browser window will open for you to authorize access.
Usage: python setup_sheets.py
"""

import os
from dotenv import load_dotenv

load_dotenv()

import gspread

CREDENTIALS_DIR = os.path.dirname(os.path.abspath(__file__))

HDJ_HEADERS = [
    "N Dossier", "Nom", "Prenom", "Age", "Sexe", "Adresse",
    "Date de visite", "Tension arterielle", "Frequence cardiaque",
    "Examen", "Clinique", "Diagnostic final", "Antecedents",
    "Traitement en cours", "Decision finale", "Evolution", "Note",
    "Date d'insertion"
]

BLOC_HEADERS = [
    "N Dossier", "Nom", "Prenom", "Age", "Sexe", "Diagnostic",
    "Type d'intervention", "Date d'intervention", "Operateur",
    "Anesthesiste", "Decision", "Resultat d'operation", "Complications",
    "Duree", "Suivi post-op", "Note", "Date d'insertion"
]


def create_spreadsheet():
    client_secret_file = os.path.join(CREDENTIALS_DIR, "client_secret.json")
    authorized_user_file = os.path.join(CREDENTIALS_DIR, "authorized_user.json")

    if not os.path.exists(client_secret_file):
        print(f"ERREUR: Fichier client_secret.json introuvable dans {CREDENTIALS_DIR}")
        print("Assurez-vous que le fichier existe avec vos Google Client ID et Secret.")
        return

    print("Authentification Google en cours...")
    print("(Une fenetre de navigateur va s'ouvrir pour l'autorisation)")
    print()

    client = gspread.oauth(
        credentials_filename=client_secret_file,
        authorized_user_filename=authorized_user_file,
    )

    print("Authentification reussie!")
    print("Creation du spreadsheet CardioBot...")

    spreadsheet = client.create("CardioBot - Patients Cardiologie")

    # Setup HDJ sheet
    hdj_sheet = spreadsheet.sheet1
    hdj_sheet.update_title("HDJ")
    hdj_sheet.append_row(HDJ_HEADERS, value_input_option="USER_ENTERED")
    hdj_sheet.freeze(rows=1)
    hdj_sheet.format("1:1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.85, "green": 0.92, "blue": 0.98}
    })

    # Setup Bloc sheet
    bloc_sheet = spreadsheet.add_worksheet(title="Bloc Operatoire", rows=1000, cols=20)
    bloc_sheet.append_row(BLOC_HEADERS, value_input_option="USER_ENTERED")
    bloc_sheet.freeze(rows=1)
    bloc_sheet.format("1:1", {
        "textFormat": {"bold": True},
        "backgroundColor": {"red": 0.98, "green": 0.85, "blue": 0.85}
    })

    print()
    print("=" * 60)
    print("Spreadsheet cree avec succes!")
    print(f"  Nom: {spreadsheet.title}")
    print(f"  ID:  {spreadsheet.id}")
    print(f"  URL: {spreadsheet.url}")
    print()
    print("Ajoutez cette ligne a votre fichier .env:")
    print(f"  SPREADSHEET_ID={spreadsheet.id}")
    print("=" * 60)


if __name__ == "__main__":
    create_spreadsheet()
