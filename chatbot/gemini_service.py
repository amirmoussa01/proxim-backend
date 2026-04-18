import google.generativeai as genai
from django.conf import settings
from services.models import Service, Category
from accounts.models import User


def get_context_from_db(message: str) -> str:
    """Interroge la DB selon le message pour enrichir le contexte."""
    context = ""
    message_lower = message.lower()

    # Chercher des services correspondants
    services = Service.objects.filter(
        is_available=True
    ).select_related('prestatire', 'categorie')

    # Filtrer si mot-clé détecté
    mots_cles = message_lower.split()
    services_filtres = services.filter(
        titre__icontains=message_lower
    ) | services.filter(
        description__icontains=message_lower
    ) | services.filter(
        categorie__nom__icontains=message_lower
    )

    if services_filtres.exists():
        context += "\n=== SERVICES DISPONIBLES SUR PROXIM ===\n"
        for s in services_filtres[:5]:
            prix = f"{s.prix_base} {s.devise}" if s.prix_base else "Sur devis"
            localisation = s.localisation or (
                f"{s.prestatire.localisation}" if hasattr(s.prestatire, 'localisation') else "Non précisé"
            )
            context += (
                f"- {s.titre} | Prestataire: {s.prestatire.user.get_full_name()} "
                f"| Prix: {prix} | Localisation: {localisation} "
                f"| Catégorie: {s.categorie.nom}\n"
            )
    else:
        # Donner un aperçu général des catégories disponibles
        categories = Category.objects.filter(is_active=True)
        if categories.exists():
            noms = ", ".join([c.nom for c in categories])
            context += f"\n=== CATÉGORIES DISPONIBLES ===\n{noms}\n"

        # Nombre de prestataires actifs
        nb_presta = User.objects.filter(is_prestataire=True, is_active=True).count()
        context += f"\nNombre de prestataires actifs sur Proxim : {nb_presta}\n"

    return context


def get_system_prompt() -> str:
    return """Tu es l'assistant virtuel de Proxim, une marketplace de services au Bénin.

Ton rôle :
- Aider les clients à trouver des services (électricité, plomberie, ménage, etc.)
- Expliquer comment fonctionne la plateforme
- Répondre aux questions sur les prix, disponibilités, prestataires
- Guider les clients pour passer une commande

Comment fonctionne Proxim :
- Le client cherche un service dans la liste ou via la recherche
- Il clique sur un service pour voir les détails
- Il clique sur "Commander" et remplit le formulaire
- Le prestataire reçoit la commande et l'accepte ou la refuse
- Le paiement se fait via KKiaPay (mobile money ou carte)
- Après service rendu, le client peut noter le prestataire

Règles importantes :
- Réponds toujours en français
- Sois concis et utile (max 3-4 phrases par réponse)
- Si tu ne sais pas, dis-le honnêtement
- Ne promets pas ce que la plateforme ne fait pas
- Utilise les données de la base de données fournies en contexte pour répondre précisément
"""


def chat_with_gemini(message: str, historique: list) -> str:
    """
    Envoie le message à Gemini avec le contexte DB et l'historique.
    historique : liste de dicts {role: 'user'|'model', parts: [text]}
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name='gemini-1.5-flash',
            system_instruction=get_system_prompt(),
        )

        # Enrichir avec contexte DB
        contexte_db = get_context_from_db(message)

        # Construire l'historique Gemini
        history = []
        for item in historique:
            history.append({
                'role': item['role'],
                'parts': [item['content']]
            })

        chat = model.start_chat(history=history)

        # Message enrichi avec contexte si pertinent
        message_enrichi = message
        if contexte_db:
            message_enrichi = (
                f"{message}\n\n[Contexte base de données Proxim]{contexte_db}"
            )

        response = chat.send_message(message_enrichi)
        return response.text

    except Exception as e:
        return "Désolé, je rencontre un problème technique. Réessayez dans quelques instants."