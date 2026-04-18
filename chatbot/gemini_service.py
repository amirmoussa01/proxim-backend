from google import genai
from google.genai import types
from django.conf import settings
from services.models import Service, Category
from accounts.models import User


def get_context_from_db(message: str) -> str:
    """Interroge la DB selon le message pour enrichir le contexte."""
    context = ""
    message_lower = message.lower()

    services_filtres = Service.objects.filter(
        is_available=True
    ).filter(
        titre__icontains=message_lower
    ) | Service.objects.filter(
        is_available=True,
        description__icontains=message_lower
    ) | Service.objects.filter(
        is_available=True,
        categorie__nom__icontains=message_lower
    )

    services_filtres = services_filtres.select_related(
        'prestatire', 'prestatire__user', 'categorie'
    ).distinct()

    if services_filtres.exists():
        context += "\n=== SERVICES DISPONIBLES SUR PROXIM ===\n"
        for s in services_filtres[:5]:
            prix = f"{s.prix_base} {s.devise}" if s.prix_base else "Sur devis"
            localisation = s.localisation or "Non précisé"
            nom_presta = ""
            try:
                nom_presta = s.prestatire.user.get_full_name()
            except Exception:
                nom_presta = "Prestataire"
            context += (
                f"- {s.titre} | Prestataire: {nom_presta} "
                f"| Prix: {prix} | Localisation: {localisation} "
                f"| Catégorie: {s.categorie.nom}\n"
            )
    else:
        categories = Category.objects.filter(is_active=True)
        if categories.exists():
            noms = ", ".join([c.nom for c in categories])
            context += f"\n=== CATÉGORIES DISPONIBLES ===\n{noms}\n"

        nb_presta = User.objects.filter(
            is_prestataire=True, is_active=True
        ).count()
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
    Envoie le message à Gemini avec contexte DB et historique de session.
    historique : liste de dicts {role: 'user'|'model', content: '...'}
    """
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)

        # Enrichir avec contexte DB
        contexte_db = get_context_from_db(message)
        message_enrichi = message
        if contexte_db:
            message_enrichi = (
                f"{message}\n\n[Contexte base de données Proxim]{contexte_db}"
            )

        # Construire l'historique au format Gemini
        history = []
        for item in historique[-10:]:
            role = item.get('role', 'user')
            content = item.get('content', '')
            history.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=content)]
                )
            )

        # Ajouter le message actuel
        history.append(
            types.Content(
                role='user',
                parts=[types.Part(text=message_enrichi)]
            )
        )

        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=get_system_prompt(),
                max_output_tokens=500,
                temperature=0.7,
            ),
        )

        return response.text

    except Exception as e:
        return (
            "Désolé, je rencontre un problème technique. "
            "Réessayez dans quelques instants."
        )