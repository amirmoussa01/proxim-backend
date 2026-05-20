from groq import Groq
from django.conf import settings
from services.models import Service, Category
from django.contrib.auth import get_user_model

User = get_user_model()


def get_context_from_db(message: str) -> str:
    context = ""
    message_lower = message.lower()

    services_filtres = (
        Service.objects.filter(is_available=True, titre__icontains=message_lower) |
        Service.objects.filter(is_available=True, description__icontains=message_lower) |
        Service.objects.filter(is_available=True, categorie__nom__icontains=message_lower)
    ).select_related('prestatire', 'prestatire__user', 'categorie').distinct()

    if services_filtres.exists():
        context += "\n=== SERVICES DISPONIBLES SUR PROXIM ===\n"
        for s in services_filtres[:5]:
            prix = f"{s.prix_base} {s.devise}" if s.prix_base else "Sur devis"
            localisation = s.localisation or "Non précisé"
            try:
                u = s.prestatire.user
                nom_presta = f"{u.first_name} {u.last_name}".strip() or u.email
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
            role=User.ROLE_PRESTATAIRE, is_active=True
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
- Ne jamais divulguer ou partages des informations de contact des prestataires(email, numero de telephone, etc..) afin d'eviter la communication hors de la plateforme
"""


def chat_with_gemini(message: str, historique: list) -> str:
    try:
        client = Groq(api_key=settings.GEMINI_API_KEY)

        contexte_db = get_context_from_db(message)
        message_enrichi = message
        if contexte_db:
            message_enrichi = (
                f"{message}\n\n[Contexte base de données Proxim]{contexte_db}"
            )

        # Construire les messages au format OpenAI/Groq
        messages = [
            {"role": "system", "content": get_system_prompt()}
        ]

        # Ajouter l'historique
        for item in historique[-10:]:
            role = item.get('role', 'user')
            # Groq utilise 'assistant' au lieu de 'model'
            if role == 'model':
                role = 'assistant'
            messages.append({
                "role": role,
                "content": item.get('content', '')
            })

        # Ajouter le message actuel enrichi
        messages.append({
            "role": "user",
            "content": message_enrichi
        })

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )

        return response.choices[0].message.content

    except Exception as e:
        import traceback
        print("ERREUR CHATBOT:", str(e))
        print(traceback.format_exc())
        return (
            "Désolé, je rencontre un problème technique. "
            "Réessayez dans quelques instants."
        )