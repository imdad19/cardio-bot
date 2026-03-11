# CardioBot -- Assistant Cardiologie

An AI-powered Telegram bot for cardiologists to manage patient records via natural language.
Built with **Claude API** (AI parsing) + **Google Sheets** (database) + **Notion** (optional) + **python-telegram-bot**.

---

## Features

| Feature | Description |
|---|---|
| Free-text input | Dictate patient info naturally in French or English |
| AI extraction | Claude automatically parses name, age, diagnosis, BP, exams, etc. |
| Two sheets | HDJ (day hospital) and Bloc Operatoire (surgery) |
| Google Sheets DB | All patients stored in a structured, searchable spreadsheet |
| Smart search | Search by name, dossier number, or diagnosis across both sheets |
| Updates | Update any patient field via natural language |
| Dashboard | Visual charts with patient stats, exam distribution, diagnoses |
| Medical suggestions | AI-powered clinical suggestions based on case data |
| Case analysis | Analyze trends, compare outcomes, query historical data |
| Memory | Bot remembers context within each conversation session |
| Access control | Restrict bot to specific Telegram user IDs |

---

## Setup

### 1. Get API Keys

**Telegram Bot:**
1. Open Telegram, search `@BotFather`
2. Send `/newbot`, follow prompts
3. Copy the token

**Claude API:**
1. Go to https://console.anthropic.com
2. Create an API key

**Google Sheets (OAuth2):**
1. Go to https://console.cloud.google.com
2. Create a project (or select existing)
3. Enable Google Sheets API and Google Drive API
4. Go to Credentials > Create Credentials > OAuth client ID
5. Application type: **Desktop app**
6. Copy the Client ID and Client Secret

**Notion (optional):**
1. Go to https://www.notion.so/my-integrations
2. Create integration, copy the token

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual keys
```

Save your Google OAuth credentials as `client_secret.json`:
```json
{
    "installed": {
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}
```

### 4. Create Google Spreadsheet

```bash
python setup_sheets.py
# A browser window will open for Google authorization
# Copy the SPREADSHEET_ID from the output and add it to .env
```

### 5. Create Notion Database (optional)

```bash
# Set NOTION_PAGE_ID in .env first
python setup_notion.py
```

### 6. Run the Bot

```bash
python bot.py
```

---

## Usage Examples

### Add a Patient (HDJ)
```
Patient Benali Ahmed, 65 ans, homme, adresse Alger centre.
ETT realisee a la clinique El-Azhar.
Diagnostic: insuffisance mitrale grade II.
Tension 14/9, FC 78.
Decision: surveillance et traitement medical.
Dossier 2547.
```

### Add a Patient (Bloc)
```
Bloc operatoire: patient Khedim Sara, 72 ans, femme.
Coronarographie prevue. Decision: pose de stent.
Operateur Dr. Meziane.
```

### Search a Patient
```
Montre-moi le dossier de Benali
Cherche le patient 2547
```

### Get Medical Suggestions
```
Que faire pour un patient de 70 ans avec FA paroxystique et FEVG 35%?
Suggestions pour le cas de Benali
Conduite a tenir devant une insuffisance mitrale severe?
```

### Analyze Data
```
Combien de patients ce mois?
Resume les cas d'ETT de cette semaine
Compare les resultats des patients de plus de 70 ans
```

---

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu |
| `/help` | Show all commands |
| `/hdj` | Recent HDJ patients |
| `/bloc` | Recent Bloc patients |
| `/dashboard` | Visual statistics dashboard |
| `/clear` | Clear conversation memory |

---

## Architecture

```
Telegram Message
      |
  bot.py (handler)
      |
  Claude API (parse intent + extract structured data)
      |
  +-----------------------------------+
  | ADD_HDJ / ADD_BLOC / SEARCH /     |
  | UPDATE / LIST / ANALYZE /         |
  | SUGGEST / ANSWER                  |
  +-----------------------------------+
      |
  Google Sheets API (read/write patient data)
      |
  Formatted reply -> Telegram
```

---

## Google Sheets Schema

### Sheet 1: HDJ (Hopital De Jour)

| Column | Description |
|---|---|
| N Dossier | Patient file number |
| Nom / Prenom | Full name |
| Age / Sexe | Demographics |
| Adresse | Address |
| Date de visite | Consultation date |
| Tension arterielle | Blood pressure |
| Frequence cardiaque | Heart rate (bpm) |
| Examen | ETT / ETO / ECG / Holter / Stress test |
| Clinique | Hospital / clinic name |
| Diagnostic final | Final cardiac diagnosis |
| Antecedents | Medical history |
| Traitement en cours | Current medications |
| Decision finale | Treatment decision |
| Evolution | Clinical evolution |
| Note | Free-form notes |
| Date d'insertion | Auto timestamp |

### Sheet 2: Bloc Operatoire

| Column | Description |
|---|---|
| N Dossier | Patient file number |
| Nom / Prenom / Age / Sexe | Demographics |
| Diagnostic | Pre-operative diagnosis |
| Type d'intervention | Procedure type |
| Date d'intervention | Surgery date |
| Operateur | Surgeon |
| Anesthesiste | Anesthesiologist |
| Decision | Decision taken |
| Resultat d'operation | Post-operative result |
| Complications | Complications |
| Duree | Duration |
| Suivi post-op | Follow-up instructions |
| Note | Free-form notes |
| Date d'insertion | Auto timestamp |

---

## Security

- Set `ALLOWED_USER_IDS` to restrict access
- Never commit `.env` or `client_secret.json` to git
- Conversation history is in-memory only (cleared on restart or `/clear`)

---

## File Structure

```
cardio-bot/
  bot.py              # Main Telegram bot
  sheets.py           # Google Sheets CRUD operations
  dashboard.py        # Chart generation (matplotlib)
  setup_sheets.py     # One-time spreadsheet creation
  setup_notion.py     # One-time Notion DB creation (optional)
  client_secret.json  # Google OAuth credentials (not committed)
  .env                # Environment variables (not committed)
  .env.example        # Template for .env
  .gitignore          # Git ignore rules
  requirements.txt    # Python dependencies
  README.md           # This file
```
