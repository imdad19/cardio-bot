"""
CardioBot -- Telegram bot for cardiologist patient management
Uses Claude API for AI parsing + Google Sheets as patient database
Two sheets: HDJ (Hopital De Jour) and Bloc Operatoire
"""

import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import anthropic

from sheets import (
    add_hdj_patient, add_bloc_patient,
    get_hdj_patients, get_bloc_patients,
    search_all_patients, update_hdj_patient, update_bloc_patient,
    get_all_data_for_analysis, get_stats,
    format_hdj_patient, format_bloc_patient,
    upload_image_to_drive, append_image_to_patient,
)
from dashboard import generate_dashboard

# -- Logging ------------------------------------------------------------------
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -- Config -------------------------------------------------------------------
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
ALLOWED_USER_IDS   = list(map(int, os.environ.get("ALLOWED_USER_IDS", "").split(","))) if os.environ.get("ALLOWED_USER_IDS") else []

# -- Clients ------------------------------------------------------------------
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# -- In-memory conversation history per user ----------------------------------
conversation_histories: dict[int, list] = {}


# =============================================================================
# CLAUDE AI
# =============================================================================

SYSTEM_PROMPT = """Tu es CardioBot, un assistant medical intelligent pour Dr. Najib, cardiologue.
Tu geres les dossiers patients stockes dans Google Sheets avec deux feuilles:

1. HDJ (Hopital De Jour): pour les consultations, echocardiographies (ETT/ETO), suivis
2. Bloc Operatoire: pour les interventions chirurgicales et catheterismes cardiaques

Tu communiques en francais et en anglais selon la langue de l'utilisateur.
IMPORTANT: N'utilise JAMAIS d'emojis dans tes reponses. Garde un ton professionnel et sobre.

Tu as ces capacites:
- ADD_HDJ: Ajouter un patient en consultation/HDJ
- ADD_BLOC: Ajouter un patient pour le bloc operatoire
- SEARCH_PATIENT: Chercher un patient par nom, numero de dossier, ou diagnostic
- UPDATE_HDJ: Mettre a jour un dossier HDJ
- UPDATE_BLOC: Mettre a jour un dossier bloc
- LIST_HDJ: Lister les patients HDJ recents
- LIST_BLOC: Lister les patients bloc recents
- ANALYZE: Analyser les donnees patients (statistiques, tendances, comparaisons)
- SUGGEST: Fournir des suggestions medicales basees sur un cas clinique ou un patient existant
- ANSWER: Repondre a une question medicale ou generale

Quand l'utilisateur fournit des informations patient, extrais les champs disponibles.

REPONDS TOUJOURS avec cette structure JSON:
```json
{
  "action": "ADD_HDJ" | "ADD_BLOC" | "SEARCH_PATIENT" | "UPDATE_HDJ" | "UPDATE_BLOC" | "LIST_HDJ" | "LIST_BLOC" | "ANALYZE" | "SUGGEST" | "ANSWER",
  "data": { ... },
  "message": "Reponse lisible dans la langue de l'utilisateur"
}
```

Pour ADD_HDJ, extrais ces champs (tous optionnels sauf nom):
- nom, prenom, age (entier), sexe (Homme/Femme),
  diagnostic_final,
  clinique (presentation clinique: symptomes et signes comme dyspnee, douleur thoracique, palpitations, syncope, oedemes...),
  medecin_referant (medecin qui a adresse le patient),
  decision_finale,
  telephone (numero de telephone, commence par 05, 06 ou 07),
  adresse, date_visite, tension, frequence_cardiaque,
  examen (ETT/ETO/ECG/Holter/Epreuve d'effort),
  antecedents, traitement, evolution, note

Pour ADD_BLOC, extrais:
- nom, prenom, age, sexe,
  diagnostic,
  clinique (presentation clinique: symptomes et signes),
  medecin_referant (medecin qui a adresse le patient),
  decision,
  telephone (numero de telephone, commence par 05, 06 ou 07),
  type_intervention,
  date_intervention, operateur, anesthesiste,
  resultat_operation, complications, duree, suivi_postop, note

Pour SEARCH_PATIENT: data = {"query": "terme de recherche"}
Pour UPDATE_HDJ: data = {"query": "nom patient", "updates": {champs a modifier}}
Pour UPDATE_BLOC: data = {"query": "nom patient", "updates": {champs a modifier}}
Pour LIST_HDJ / LIST_BLOC: data = {}
Pour ANALYZE: data = {"query": "la question d'analyse"}
Pour SUGGEST: data = {"query": "nom du patient ou description du cas", "context": "informations supplementaires"}
  - Quand l'utilisateur demande des suggestions, fournis:
    * Examens complementaires recommandes
    * Options therapeutiques possibles
    * Points de vigilance clinique
    * Recommandations de suivi
    * References aux guidelines ESC/AHA si pertinent
  - IMPORTANT: Rappelle toujours que les suggestions ne remplacent pas le jugement clinique du praticien
Pour ANSWER: data = {"response": "ta reponse"}

Determine intelligemment si un patient va en HDJ ou au Bloc:
- Mots-cles HDJ: ETT, ETO, consultation, suivi, controle, visite, echocardiographie, holter, ECG
- Mots-cles Bloc: operation, bloc, chirurgie, intervention, coronarographie, stent, ablation, catheterisme, pontage

Determine si l'utilisateur demande une suggestion:
- Mots-cles: suggestion, suggere, recommande, que faire, conduite a tenir, quoi faire, propose, avis, conseil, what should, recommend, advise, opinion

Sois concis, professionnel et medicalement precis. N'invente jamais de donnees patient."""


def get_ai_response(user_id: int, user_message: str, context_data: str = "") -> dict:
    """Get structured response from Claude with optional data context."""
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    if context_data:
        full_message = (
            f"[DONNEES ACTUELLES DE LA BASE]\n{context_data}\n\n"
            f"[MESSAGE UTILISATEUR]\n{user_message}"
        )
    else:
        full_message = user_message

    conversation_histories[user_id].append({"role": "user", "content": full_message})

    # Keep last 20 messages
    history = conversation_histories[user_id][-20:]

    response = claude.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        system=SYSTEM_PROMPT,
        messages=history
    )

    raw = response.content[0].text
    conversation_histories[user_id].append({"role": "assistant", "content": raw})

    # Parse JSON from response
    try:
        start = raw.find("```json") + 7
        end = raw.find("```", start)
        if start > 6 and end > start:
            json_str = raw[start:end].strip()
        else:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            json_str = raw[start:end]
        return json.loads(json_str)
    except Exception:
        return {"action": "ANSWER", "data": {"response": raw}, "message": raw}


def _load_context_data() -> str:
    """Load patient data from both sheets for context-aware responses."""
    try:
        all_data = get_all_data_for_analysis()
        hdj_summary = json.dumps(all_data["hdj"][-50:], ensure_ascii=False, indent=2) if all_data["hdj"] else "Aucune donnee HDJ"
        bloc_summary = json.dumps(all_data["bloc"][-50:], ensure_ascii=False, indent=2) if all_data["bloc"] else "Aucune donnee Bloc"
        return f"HDJ ({len(all_data['hdj'])} patients):\n{hdj_summary}\n\nBloc Operatoire ({len(all_data['bloc'])} patients):\n{bloc_summary}"
    except Exception as e:
        logger.warning(f"Could not load data for context: {e}")
        return ""


# Keywords that trigger data loading for context-aware responses
CONTEXT_KEYWORDS = [
    # Analysis
    "combien", "statistique", "analyse", "resume", "compare",
    "tendance", "evolution", "total", "moyenne", "how many",
    "summary", "analyze", "trend", "patients ce mois",
    "patients cette semaine", "precedent", "dernier",
    "historique", "donnees", "previous", "last",
    # Suggestions
    "suggestion", "suggere", "recommande", "que faire",
    "conduite a tenir", "quoi faire", "propose", "avis",
    "conseil", "what should", "recommend", "advise", "opinion",
    # Case queries
    "cas de", "dossier de", "patient", "montre", "cherche",
    "find", "show", "search",
]


# =============================================================================
# TELEGRAM HANDLERS
# =============================================================================

def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Acces non autorise.")
        return

    keyboard = [
        [InlineKeyboardButton("Nouveau patient HDJ", callback_data="help_add_hdj"),
         InlineKeyboardButton("Nouveau patient Bloc", callback_data="help_add_bloc")],
        [InlineKeyboardButton("Rechercher", callback_data="help_search"),
         InlineKeyboardButton("Suggestion medicale", callback_data="help_suggest")],
        [InlineKeyboardButton("Patients HDJ", callback_data="list_hdj"),
         InlineKeyboardButton("Patients Bloc", callback_data="list_bloc")],
        [InlineKeyboardButton("Tableau de bord", callback_data="dashboard")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "*CardioBot -- Assistant Cardiologie*\n\n"
        "Bienvenue, Dr. Najib. Je suis votre assistant pour gerer vos dossiers patients.\n\n"
        "Vous pouvez:\n"
        "- Dicter les infos d'un patient en texte libre\n"
        "- Chercher un patient par nom ou numero de dossier\n"
        "- Consulter les dossiers recents (HDJ ou Bloc)\n"
        "- Voir le tableau de bord avec les statistiques\n"
        "- Demander des suggestions medicales sur un cas\n"
        "- Poser des questions sur vos cas precedents\n"
        "- Demander une analyse de vos donnees\n\n"
        "Tapez /help pour voir toutes les commandes.",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "*Commandes disponibles:*\n\n"
        "/start -- Menu principal\n"
        "/hdj -- Patients HDJ recents\n"
        "/bloc -- Patients Bloc recents\n"
        "/dashboard -- Tableau de bord (graphiques)\n"
        "/clear -- Effacer l'historique de conversation\n"
        "/help -- Afficher cette aide\n\n"
        "*En texte libre, vous pouvez:*\n"
        "- Ajouter un patient (dictez les informations)\n"
        "- Rechercher un patient (nom, dossier, diagnostic)\n"
        "- Mettre a jour un dossier existant\n"
        "- Demander une suggestion medicale sur un cas\n"
        "- Analyser les donnees de vos patients\n"
        "- Poser des questions medicales generales",
        parse_mode="Markdown"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversation_histories.pop(user_id, None)
    await update.message.reply_text("Historique de conversation efface.")


async def _send_hdj_list(chat_message, context: ContextTypes.DEFAULT_TYPE):
    """Send HDJ patient list to a chat message (works with both messages and callback queries)."""
    try:
        patients = get_hdj_patients(10)
        if not patients:
            await chat_message.reply_text("Aucun patient HDJ trouve.")
            return
        text = f"*{len(patients)} patients HDJ recents:*\n\n"
        for p in patients:
            nom = p.get("Nom", "")
            prenom = p.get("Prenom", "")
            diag = str(p.get("Diagnostic final", ""))[:40]
            date = p.get("Date de visite", "")
            text += f"- *{prenom} {nom}*"
            if diag:
                text += f" -- {diag}"
            if date:
                text += f" ({date})"
            text += "\n"
        await chat_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing HDJ: {e}")
        await chat_message.reply_text(f"Erreur lors de la recuperation: {str(e)[:200]}")


async def _send_bloc_list(chat_message, context: ContextTypes.DEFAULT_TYPE):
    """Send Bloc patient list to a chat message."""
    try:
        patients = get_bloc_patients(10)
        if not patients:
            await chat_message.reply_text("Aucun patient au Bloc Operatoire.")
            return
        text = f"*{len(patients)} patients Bloc recents:*\n\n"
        for p in patients:
            nom = p.get("Nom", "")
            prenom = p.get("Prenom", "")
            intervention = str(p.get("Type d'intervention", ""))[:40]
            date = p.get("Date d'intervention", "")
            text += f"- *{prenom} {nom}*"
            if intervention:
                text += f" -- {intervention}"
            if date:
                text += f" ({date})"
            text += "\n"
        await chat_message.reply_text(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing Bloc: {e}")
        await chat_message.reply_text(f"Erreur lors de la recuperation: {str(e)[:200]}")


async def _send_dashboard(chat_message, context: ContextTypes.DEFAULT_TYPE):
    """Generate and send the dashboard chart."""
    try:
        stats = get_stats()
        dashboard_path = generate_dashboard(stats)
        with open(dashboard_path, "rb") as photo:
            await chat_message.reply_photo(
                photo=photo,
                caption="Tableau de bord -- CardioBot Cardiologie"
            )
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        await chat_message.reply_text(f"Erreur lors de la generation du tableau de bord: {str(e)[:200]}")


async def cmd_hdj(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("Recuperation des patients HDJ recents...")
    await _send_hdj_list(update.message, context)


async def cmd_bloc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("Recuperation des patients Bloc recents...")
    await _send_bloc_list(update.message, context)


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text("Generation du tableau de bord...")
    await _send_dashboard(update.message, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help_add_hdj":
        await query.message.reply_text(
            "*Ajouter un patient HDJ*\n\n"
            "Envoyez les informations en texte libre, par exemple:\n\n"
            "_Patient Benali Ahmed, 65 ans, homme, adresse Alger centre. "
            "ETT realisee a la clinique El-Azhar. "
            "Diagnostic: insuffisance mitrale grade II. "
            "Tension 14/9, FC 78. "
            "Decision: surveillance et traitement medical. "
            "Dossier 2547._\n\n"
            "Les donnees seront extraites et sauvegardees automatiquement.",
            parse_mode="Markdown"
        )
    elif query.data == "help_add_bloc":
        await query.message.reply_text(
            "*Ajouter un patient Bloc Operatoire*\n\n"
            "Envoyez les informations en texte libre, par exemple:\n\n"
            "_Bloc operatoire: patient Khedim Sara, 72 ans, femme. "
            "Coronarographie prevue. Decision: pose de stent. "
            "Operateur Dr. Meziane._\n\n"
            "Les donnees seront extraites et sauvegardees automatiquement.",
            parse_mode="Markdown"
        )
    elif query.data == "help_search":
        await query.message.reply_text(
            "*Rechercher un patient*\n\n"
            "Exemples:\n"
            "- _Montre-moi le dossier de Benali_\n"
            "- _Cherche le patient 2547_\n"
            "- _Find patient with myocarditis_\n"
            "- _Qui a ete opere la semaine derniere?_",
            parse_mode="Markdown"
        )
    elif query.data == "help_suggest":
        await query.message.reply_text(
            "*Suggestions medicales*\n\n"
            "Demandez des suggestions sur un cas clinique:\n\n"
            "- _Que faire pour un patient de 70 ans avec FA paroxystique?_\n"
            "- _Suggestions pour le cas de Benali_\n"
            "- _Conduite a tenir devant une insuffisance mitrale severe?_\n"
            "- _Quels examens complementaires pour une douleur thoracique atypique?_\n\n"
            "Le bot peut aussi analyser un cas existant dans la base.",
            parse_mode="Markdown"
        )
    elif query.data == "list_hdj":
        await query.message.reply_text("Recuperation des patients HDJ recents...")
        await _send_hdj_list(query.message, context)
    elif query.data == "list_bloc":
        await query.message.reply_text("Recuperation des patients Bloc recents...")
        await _send_bloc_list(query.message, context)
    elif query.data == "dashboard":
        await query.message.reply_text("Generation du tableau de bord...")
        await _send_dashboard(query.message, context)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Acces non autorise.")
        return

    user_id = update.effective_user.id
    user_text = update.message.text.strip()

    # Typing indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Load data context if the message seems to need it
    context_data = ""
    if any(kw in user_text.lower() for kw in CONTEXT_KEYWORDS):
        context_data = _load_context_data()

    # Get AI structured response
    ai_result = get_ai_response(user_id, user_text, context_data)
    action = ai_result.get("action", "ANSWER")
    data = ai_result.get("data", {})
    message = ai_result.get("message", "Je n'ai pas compris.")

    # -- ADD HDJ ---------------------------------------------------------------
    if action == "ADD_HDJ":
        try:
            patient_name = add_hdj_patient(data)
            await update.message.reply_text(
                f"*Dossier HDJ cree:* {patient_name}\n\n{message}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Sheets add HDJ error: {e}")
            await update.message.reply_text(
                f"Donnees extraites mais erreur Google Sheets:\n`{str(e)[:200]}`\n\n{message}",
                parse_mode="Markdown"
            )

    # -- ADD BLOC --------------------------------------------------------------
    elif action == "ADD_BLOC":
        try:
            patient_name = add_bloc_patient(data)
            await update.message.reply_text(
                f"*Dossier Bloc cree:* {patient_name}\n\n{message}",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Sheets add Bloc error: {e}")
            await update.message.reply_text(
                f"Donnees extraites mais erreur Google Sheets:\n`{str(e)[:200]}`\n\n{message}",
                parse_mode="Markdown"
            )

    # -- SEARCH PATIENT --------------------------------------------------------
    elif action == "SEARCH_PATIENT":
        query_term = data.get("query", user_text)
        try:
            results = search_all_patients(query_term)
            hdj_results = results["hdj"]
            bloc_results = results["bloc"]

            if not hdj_results and not bloc_results:
                await update.message.reply_text(
                    f"Aucun patient trouve pour \"{query_term}\".\n"
                    "Verifiez l'orthographe ou essayez le numero de dossier."
                )
            else:
                text = ""
                if hdj_results:
                    text += f"*-- HDJ ({len(hdj_results)} resultat(s)) --*\n\n"
                    for p in hdj_results[:5]:
                        text += format_hdj_patient(p) + "\n\n"
                if bloc_results:
                    text += f"*-- Bloc Operatoire ({len(bloc_results)} resultat(s)) --*\n\n"
                    for p in bloc_results[:5]:
                        text += format_bloc_patient(p) + "\n\n"
                if len(text) > 4000:
                    text = text[:4000] + "\n\n... (resultats tronques)"
                await update.message.reply_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text(f"Erreur de recherche: {str(e)[:200]}")

    # -- UPDATE HDJ ------------------------------------------------------------
    elif action == "UPDATE_HDJ":
        query_term = data.get("query", "")
        updates = data.get("updates", {})
        try:
            success, name = update_hdj_patient(query_term, updates)
            if success:
                await update.message.reply_text(
                    f"Dossier HDJ de *{name}* mis a jour.\n\n{message}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"Patient \"{query_term}\" introuvable dans HDJ."
                )
        except Exception as e:
            logger.error(f"Update HDJ error: {e}")
            await update.message.reply_text(f"Erreur de mise a jour: {str(e)[:200]}")

    # -- UPDATE BLOC -----------------------------------------------------------
    elif action == "UPDATE_BLOC":
        query_term = data.get("query", "")
        updates = data.get("updates", {})
        try:
            success, name = update_bloc_patient(query_term, updates)
            if success:
                await update.message.reply_text(
                    f"Dossier Bloc de *{name}* mis a jour.\n\n{message}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"Patient \"{query_term}\" introuvable au Bloc."
                )
        except Exception as e:
            logger.error(f"Update Bloc error: {e}")
            await update.message.reply_text(f"Erreur de mise a jour: {str(e)[:200]}")

    # -- LIST HDJ --------------------------------------------------------------
    elif action == "LIST_HDJ":
        await _send_hdj_list(update.message, context)

    # -- LIST BLOC -------------------------------------------------------------
    elif action == "LIST_BLOC":
        await _send_bloc_list(update.message, context)

    # -- SUGGEST ---------------------------------------------------------------
    elif action == "SUGGEST":
        # If no context was loaded yet but user is asking about a specific patient, try to load
        if not context_data:
            context_data = _load_context_data()
            if context_data:
                # Re-ask Claude with the data
                ai_result = get_ai_response(user_id, user_text, context_data)
                message = ai_result.get("message", message)
        if len(message) > 4000:
            # Split long suggestions
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(message, parse_mode="Markdown")

    # -- ANALYZE ---------------------------------------------------------------
    elif action == "ANALYZE":
        if not context_data:
            context_data = _load_context_data()
            if context_data:
                ai_result = get_ai_response(user_id, user_text, context_data)
                message = ai_result.get("message", message)
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(message, parse_mode="Markdown")

    # -- GENERAL ANSWER --------------------------------------------------------
    else:
        if len(message) > 4000:
            parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
            for part in parts:
                await update.message.reply_text(part, parse_mode="Markdown")
        else:
            await update.message.reply_text(message, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photo messages -- upload to Google Drive and link to patient."""
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("Acces non autorise.")
        return

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    # Get the highest resolution photo
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)

    # Download to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        tmp_path = tmp.name
        await file.download_to_drive(tmp_path)

    try:
        # Name the file by patient name if provided, otherwise timestamp
        from datetime import datetime
        caption = update.message.caption or ""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if caption.strip():
            # Use patient name as filename
            safe_name = caption.strip().replace(" ", "_")
            filename = f"{safe_name}_{timestamp}.jpg"
        else:
            filename = f"cardiobot_{timestamp}.jpg"

        # Upload to Google Drive
        link = upload_image_to_drive(tmp_path, filename)

        if caption.strip():
            # Try to link to a specific patient mentioned in the caption
            # Try HDJ first, then Bloc
            success, name = append_image_to_patient("HDJ", caption.strip(), link)
            if not success:
                success, name = append_image_to_patient("Bloc Operatoire", caption.strip(), link)

            if success:
                await update.message.reply_text(
                    f"Image sauvegardee et liee au dossier de *{name}*.\n"
                    f"Lien: {link}",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    f"Image sauvegardee sur Google Drive.\n"
                    f"Patient \"{caption.strip()}\" non trouve dans la base.\n"
                    f"Lien: {link}"
                )
        else:
            await update.message.reply_text(
                f"Image sauvegardee sur Google Drive.\n"
                f"Lien: {link}\n\n"
                "Pour lier cette image a un patient, envoyez la photo "
                "avec le nom du patient en legende."
            )
    except Exception as e:
        logger.error(f"Image upload error: {e}")
        await update.message.reply_text(f"Erreur lors de l'envoi de l'image: {str(e)[:200]}")
    finally:
        import os
        os.unlink(tmp_path)


# =============================================================================
# MAIN
# =============================================================================

def main():
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(30)
        .write_timeout(30)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("help",      cmd_help))
    app.add_handler(CommandHandler("hdj",       cmd_hdj))
    app.add_handler(CommandHandler("bloc",      cmd_bloc))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("clear",     cmd_clear))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("CardioBot started -- HDJ + Bloc Operatoire")
    app.run_polling(drop_pending_updates=True, read_timeout=30, write_timeout=30)


if __name__ == "__main__":
    main()
