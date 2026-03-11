"""
sheets.py -- Google Sheets integration for CardioBot
Handles all CRUD operations for HDJ and Bloc Operatoire sheets.
Uses OAuth2 with user's Google Client ID/Secret.
"""

import os
import logging
from pathlib import Path
import gspread
from datetime import datetime

logger = logging.getLogger(__name__)

# ── Sheet headers ─────────────────────────────────────────────────────────────

HDJ_HEADERS = [
    "N Dossier", "Nom", "Prenom", "Age",
    "Clinique", "Medecin referant", "Decision finale",
    "Images", "Telephone", "Sexe", "Adresse",
    "Date de visite", "Tension arterielle", "Frequence cardiaque",
    "Examen", "Diagnostic final", "Antecedents",
    "Traitement en cours", "Evolution", "Note",
    "Date d'insertion"
]

BLOC_HEADERS = [
    "N Dossier", "Nom", "Prenom", "Age",
    "Clinique", "Medecin referant", "Decision",
    "Images", "Telephone", "Sexe",
    "Diagnostic", "Type d'intervention", "Date d'intervention", "Operateur",
    "Anesthesiste", "Resultat d'operation", "Complications",
    "Duree", "Suivi post-op", "Note",
    "Date d'insertion"
]

# ── Field mappings (AI keys -> sheet column names) ────────────────────────────

HDJ_FIELD_MAP = {
    "numero_dossier": "N Dossier",
    "nom": "Nom",
    "prenom": "Prenom",
    "age": "Age",
    "clinique": "Clinique",
    "medecin_referant": "Medecin referant",
    "decision_finale": "Decision finale",
    "telephone": "Telephone",
    "sexe": "Sexe",
    "adresse": "Adresse",
    "date_visite": "Date de visite",
    "tension": "Tension arterielle",
    "frequence_cardiaque": "Frequence cardiaque",
    "examen": "Examen",
    "diagnostic_final": "Diagnostic final",
    "antecedents": "Antecedents",
    "traitement": "Traitement en cours",
    "evolution": "Evolution",
    "note": "Note",
}

BLOC_FIELD_MAP = {
    "numero_dossier": "N Dossier",
    "nom": "Nom",
    "prenom": "Prenom",
    "age": "Age",
    "clinique": "Clinique",
    "medecin_referant": "Medecin referant",
    "decision": "Decision",
    "telephone": "Telephone",
    "sexe": "Sexe",
    "diagnostic": "Diagnostic",
    "type_intervention": "Type d'intervention",
    "date_intervention": "Date d'intervention",
    "operateur": "Operateur",
    "anesthesiste": "Anesthesiste",
    "resultat_operation": "Resultat d'operation",
    "complications": "Complications",
    "duree": "Duree",
    "suivi_postop": "Suivi post-op",
    "note": "Note",
}

# ── Google Sheets client (OAuth2) ─────────────────────────────────────────────

_client = None
_spreadsheet = None

# Use Path for robust cross-platform path resolution
_THIS_DIR = Path(__file__).resolve().parent
_CLIENT_SECRET = _THIS_DIR / "client_secret.json"
_AUTHORIZED_USER = _THIS_DIR / "authorized_user.json"


def _ensure_credentials_on_disk():
    """
    For deployed environments (Docker, etc.) where credential files may not
    exist on disk: read them from environment variables and write to disk.
    Set GOOGLE_CREDENTIALS_JSON = contents of authorized_user.json
    """
    # If authorized_user.json already exists, nothing to do
    if _AUTHORIZED_USER.exists() and _CLIENT_SECRET.exists():
        return

    # Try to create client_secret.json from env vars
    if not _CLIENT_SECRET.exists():
        client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        if client_id and client_secret:
            import json as _json
            secret_data = {
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"]
                }
            }
            _CLIENT_SECRET.write_text(_json.dumps(secret_data))
            logger.info(f"Created client_secret.json from env vars at {_CLIENT_SECRET}")

    # Try to create authorized_user.json from env var
    if not _AUTHORIZED_USER.exists():
        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
        if creds_json:
            _AUTHORIZED_USER.write_text(creds_json)
            logger.info(f"Created authorized_user.json from env var at {_AUTHORIZED_USER}")


def get_client():
    """Initialize and return the gspread client using OAuth2."""
    global _client
    if _client is None:
        _ensure_credentials_on_disk()
        logger.info(f"Google Sheets auth -- client_secret: {_CLIENT_SECRET}")
        logger.info(f"Google Sheets auth -- authorized_user: {_AUTHORIZED_USER}")
        if not _CLIENT_SECRET.exists():
            raise FileNotFoundError(
                f"client_secret.json introuvable: {_CLIENT_SECRET}. "
                "Definissez GOOGLE_CLIENT_ID et GOOGLE_CLIENT_SECRET dans les variables d'environnement."
            )
        _client = gspread.oauth(
            credentials_filename=str(_CLIENT_SECRET),
            authorized_user_filename=str(_AUTHORIZED_USER),
        )
        logger.info("Google Sheets client initialized successfully")
    return _client


DRIVE_FOLDER_ID = "1cAxaSlKqwxPUgUZFiIa4GQlYjuoQlN_N"


def upload_image_to_drive(file_path: str, filename: str) -> str:
    """Upload an image to the CardioBot Google Drive folder and return its shareable link."""
    import io
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    client = get_client()
    creds = client.auth

    drive_service = build("drive", "v3", credentials=creds)

    media = MediaFileUpload(file_path, resumable=True)
    file_metadata = {
        "name": filename,
        "parents": [DRIVE_FOLDER_ID]
    }

    file = drive_service.files().create(
        body=file_metadata, media_body=media, fields="id"
    ).execute()

    file_id = file.get("id")

    # Make it viewable by anyone with the link
    drive_service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"}
    ).execute()

    link = f"https://drive.google.com/file/d/{file_id}/view"
    logger.info(f"Image uploaded to Drive: {link}")
    return link


def append_image_to_patient(sheet_name: str, patient_query: str, image_link: str) -> tuple[bool, str]:
    """Append an image link to a patient's Images column."""
    sheet = get_sheet(sheet_name)
    all_values = sheet.get_all_records()
    headers = HDJ_HEADERS if sheet_name == "HDJ" else BLOC_HEADERS
    query_lower = patient_query.lower()

    for idx, row in enumerate(all_values):
        row_text = " ".join(str(v) for v in row.values()).lower()
        if query_lower in row_text:
            row_num = idx + 2
            if "Images" in headers:
                col_idx = headers.index("Images") + 1
                existing = str(row.get("Images", "")).strip()
                new_val = f"{existing}\n{image_link}".strip() if existing else image_link
                sheet.update_cell(row_num, col_idx, new_val)
            name = f"{row.get('Prenom', '')} {row.get('Nom', '')}".strip()
            return True, name or "Patient"
    return False, ""


def get_spreadsheet():
    """Get or open the CardioBot spreadsheet."""
    global _spreadsheet
    if _spreadsheet is None:
        client = get_client()
        spreadsheet_id = os.environ.get("SPREADSHEET_ID", "")
        if spreadsheet_id:
            _spreadsheet = client.open_by_key(spreadsheet_id)
        else:
            raise ValueError("SPREADSHEET_ID not set in environment variables.")
    return _spreadsheet


def get_sheet(sheet_name: str):
    """Get a specific worksheet by name."""
    ss = get_spreadsheet()
    return ss.worksheet(sheet_name)


# ═══════════════════════════════════════════════════════════════════════════════
# HDJ OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def add_hdj_patient(data: dict) -> str:
    """Add a patient row to the HDJ sheet."""
    sheet = get_sheet("HDJ")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    row = []
    for header in HDJ_HEADERS:
        if header == "Date d'insertion":
            row.append(now)
        elif header == "Date de visite":
            row.append(data.get("date_visite", datetime.now().strftime("%Y-%m-%d")))
        else:
            ai_key = None
            for k, v in HDJ_FIELD_MAP.items():
                if v == header:
                    ai_key = k
                    break
            value = data.get(ai_key, "") if ai_key else ""
            row.append(str(value) if value else "")

    sheet.append_row(row, value_input_option="USER_ENTERED")
    nom = data.get("nom", "")
    prenom = data.get("prenom", "")
    return f"{prenom} {nom}".strip() or "Patient"


def get_hdj_patients(limit: int = 10) -> list[dict]:
    """Fetch recent HDJ patients."""
    sheet = get_sheet("HDJ")
    all_values = sheet.get_all_records()
    if not all_values:
        return []
    return list(reversed(all_values[-limit:]))


def search_hdj_patients(query: str) -> list[dict]:
    """Search HDJ patients across all text columns."""
    sheet = get_sheet("HDJ")
    all_values = sheet.get_all_records()
    query_lower = query.lower()
    results = []
    for row in all_values:
        for value in row.values():
            if query_lower in str(value).lower():
                results.append(row)
                break
    return results


def update_hdj_patient(search_query: str, updates: dict) -> tuple[bool, str]:
    """Update an HDJ patient row. Returns (success, patient_name)."""
    sheet = get_sheet("HDJ")
    all_values = sheet.get_all_records()
    query_lower = search_query.lower()

    for idx, row in enumerate(all_values):
        row_text = " ".join(str(v) for v in row.values()).lower()
        if query_lower in row_text:
            row_num = idx + 2  # +1 for header, +1 for 1-indexing
            headers = HDJ_HEADERS
            for ai_key, value in updates.items():
                if ai_key in HDJ_FIELD_MAP and value:
                    col_name = HDJ_FIELD_MAP[ai_key]
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        sheet.update_cell(row_num, col_idx, str(value))
            name = f"{row.get('Prenom', '')} {row.get('Nom', '')}".strip()
            return True, name or "Patient"
    return False, ""


# ═══════════════════════════════════════════════════════════════════════════════
# BLOC OPERATOIRE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def add_bloc_patient(data: dict) -> str:
    """Add a patient row to the Bloc Operatoire sheet."""
    sheet = get_sheet("Bloc Operatoire")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    row = []
    for header in BLOC_HEADERS:
        if header == "Date d'insertion":
            row.append(now)
        elif header == "Date d'intervention":
            row.append(data.get("date_intervention", datetime.now().strftime("%Y-%m-%d")))
        else:
            ai_key = None
            for k, v in BLOC_FIELD_MAP.items():
                if v == header:
                    ai_key = k
                    break
            value = data.get(ai_key, "") if ai_key else ""
            row.append(str(value) if value else "")

    sheet.append_row(row, value_input_option="USER_ENTERED")
    nom = data.get("nom", "")
    prenom = data.get("prenom", "")
    return f"{prenom} {nom}".strip() or "Patient"


def get_bloc_patients(limit: int = 10) -> list[dict]:
    """Fetch recent Bloc Operatoire patients."""
    sheet = get_sheet("Bloc Operatoire")
    all_values = sheet.get_all_records()
    if not all_values:
        return []
    return list(reversed(all_values[-limit:]))


def search_bloc_patients(query: str) -> list[dict]:
    """Search Bloc patients across all text columns."""
    sheet = get_sheet("Bloc Operatoire")
    all_values = sheet.get_all_records()
    query_lower = query.lower()
    results = []
    for row in all_values:
        for value in row.values():
            if query_lower in str(value).lower():
                results.append(row)
                break
    return results


def update_bloc_patient(search_query: str, updates: dict) -> tuple[bool, str]:
    """Update a Bloc patient row."""
    sheet = get_sheet("Bloc Operatoire")
    all_values = sheet.get_all_records()
    query_lower = search_query.lower()

    for idx, row in enumerate(all_values):
        row_text = " ".join(str(v) for v in row.values()).lower()
        if query_lower in row_text:
            row_num = idx + 2
            headers = BLOC_HEADERS
            for ai_key, value in updates.items():
                if ai_key in BLOC_FIELD_MAP and value:
                    col_name = BLOC_FIELD_MAP[ai_key]
                    if col_name in headers:
                        col_idx = headers.index(col_name) + 1
                        sheet.update_cell(row_num, col_idx, str(value))
            name = f"{row.get('Prenom', '')} {row.get('Nom', '')}".strip()
            return True, name or "Patient"
    return False, ""


# ═══════════════════════════════════════════════════════════════════════════════
# CROSS-SHEET OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

def search_all_patients(query: str) -> dict:
    """Search across both sheets."""
    hdj_results = search_hdj_patients(query)
    bloc_results = search_bloc_patients(query)
    return {"hdj": hdj_results, "bloc": bloc_results}


def get_all_data_for_analysis() -> dict:
    """Get all data from both sheets for AI analysis."""
    try:
        hdj_data = get_sheet("HDJ").get_all_records()
    except Exception:
        hdj_data = []
    try:
        bloc_data = get_sheet("Bloc Operatoire").get_all_records()
    except Exception:
        bloc_data = []
    return {"hdj": hdj_data, "bloc": bloc_data}


def get_stats() -> dict:
    """Get summary statistics for the dashboard."""
    data = get_all_data_for_analysis()
    hdj = data["hdj"]
    bloc = data["bloc"]

    now = datetime.now()
    current_month = now.strftime("%Y-%m")

    hdj_this_month = 0
    for row in hdj:
        date_str = str(row.get("Date de visite", ""))
        if date_str.startswith(current_month):
            hdj_this_month += 1

    bloc_this_month = 0
    for row in bloc:
        date_str = str(row.get("Date d'intervention", ""))
        if date_str.startswith(current_month):
            bloc_this_month += 1

    exam_counts = {}
    for row in hdj:
        exam = str(row.get("Examen", "")).strip()
        if exam:
            exam_counts[exam] = exam_counts.get(exam, 0) + 1

    diag_counts = {}
    for row in hdj:
        diag = str(row.get("Diagnostic final", "")).strip()
        if diag:
            diag_counts[diag] = diag_counts.get(diag, 0) + 1
    for row in bloc:
        diag = str(row.get("Diagnostic", "")).strip()
        if diag:
            diag_counts[diag] = diag_counts.get(diag, 0) + 1

    clinique_counts = {}
    for row in hdj:
        clinique = str(row.get("Clinique", "")).strip()
        if clinique:
            clinique_counts[clinique] = clinique_counts.get(clinique, 0) + 1

    return {
        "total_hdj": len(hdj),
        "total_bloc": len(bloc),
        "hdj_this_month": hdj_this_month,
        "bloc_this_month": bloc_this_month,
        "exam_counts": exam_counts,
        "diag_counts": diag_counts,
        "clinique_counts": clinique_counts,
    }


def format_hdj_patient(row: dict) -> str:
    """Format an HDJ patient row for Telegram display."""
    lines = [f"*{row.get('Prenom', '')} {row.get('Nom', '')}*"]
    fields = [
        ("N Dossier", "Dossier"),
        ("Age", "Age"),
        ("Clinique", "Clinique"),
        ("Medecin referant", "Medecin ref."),
        ("Decision finale", "Decision"),
        ("Telephone", "Tel"),
        ("Sexe", "Sexe"),
        ("Adresse", "Adresse"),
        ("Date de visite", "Date"),
        ("Tension arterielle", "TA"),
        ("Frequence cardiaque", "FC"),
        ("Examen", "Examen"),
        ("Diagnostic final", "Diagnostic"),
        ("Antecedents", "Antecedents"),
        ("Traitement en cours", "Traitement"),
        ("Evolution", "Evolution"),
        ("Note", "Note"),
    ]
    for key, label in fields:
        val = str(row.get(key, "")).strip()
        if val:
            lines.append(f"  {label}: {val}")
    return "\n".join(lines)


def format_bloc_patient(row: dict) -> str:
    """Format a Bloc Operatoire patient row for Telegram display."""
    lines = [f"*{row.get('Prenom', '')} {row.get('Nom', '')}*"]
    fields = [
        ("N Dossier", "Dossier"),
        ("Age", "Age"),
        ("Clinique", "Clinique"),
        ("Medecin referant", "Medecin ref."),
        ("Decision", "Decision"),
        ("Telephone", "Tel"),
        ("Sexe", "Sexe"),
        ("Diagnostic", "Diagnostic"),
        ("Type d'intervention", "Intervention"),
        ("Date d'intervention", "Date"),
        ("Operateur", "Operateur"),
        ("Anesthesiste", "Anesthesiste"),
        ("Resultat d'operation", "Resultat"),
        ("Complications", "Complications"),
        ("Duree", "Duree"),
        ("Suivi post-op", "Suivi"),
        ("Note", "Note"),
    ]
    for key, label in fields:
        val = str(row.get(key, "")).strip()
        if val:
            lines.append(f"  {label}: {val}")
    return "\n".join(lines)
