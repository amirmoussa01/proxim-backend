from groq import Groq
from django.conf import settings
from services.models import Service, Category
from django.contrib.auth import get_user_model

User = get_user_model()


# ── Extraction de mots-clés depuis le message ─────────────────

def extraire_mots_cles(message: str) -> list:
    """Extrait les mots significatifs du message (ignore les mots vides)."""
    mots_vides = {
        'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles',
        'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et',
        'en', 'au', 'aux', 'sur', 'par', 'pour', 'avec', 'dans',
        'est', 'sont', 'a', 'ont', 'qui', 'que', 'quoi', 'comment',
        'cherche', 'veux', 'voudrais', 'besoin', 'trouver', 'trouver',
        'me', 'mon', 'ma', 'mes', 'pas', 'plus', 'très', 'bien',
        'avoir', 'faire', 'service', 'services', 'bonjour', 'salut',
    }
    mots = message.lower().split()
    return [m.strip('.,?!;:') for m in mots if m.strip('.,?!;:') not in mots_vides and len(m) > 2]


# ── Récupération du contexte depuis la DB ─────────────────────

def get_context_from_db(message: str) -> str:
    context = ""
    mots_cles = extraire_mots_cles(message)

    # ── 1. Recherche de services ──────────────────────────────
    if mots_cles:
        from django.db.models import Q
        query = Q()
        for mot in mots_cles:
            query |= (
                Q(titre__icontains=mot) |
                Q(description__icontains=mot) |
                Q(categorie__nom__icontains=mot) |
                Q(localisation__icontains=mot) |
                Q(prestatire__nom__icontains=mot) |
                Q(prestatire__prenom__icontains=mot)
            )

        services_filtres = Service.objects.filter(
            query, is_available=True
        ).select_related(
            'prestatire', 'prestatire__user', 'categorie'
        ).distinct()[:8]

    else:
        services_filtres = Service.objects.filter(
            is_available=True
        ).select_related(
            'prestatire', 'prestatire__user', 'categorie'
        ).order_by('-date_creation')[:6]

    if services_filtres:
        context += "\n=== SERVICES DISPONIBLES SUR PROXIM ===\n"
        for s in services_filtres:
            # Prix
            if s.pricing_type == 'SUR_DEVIS':
                prix_label = "Sur devis"
            elif s.prix_base:
                unite = ""
                if s.pricing_type == 'PAR_UNITE':
                    unite = "/unité"
                prix_label = f"{s.prix_base} {s.devise}{unite}"
            else:
                prix_label = "Sur devis"

            # Localisation
            localisation = s.localisation or "Non précisé"

            # Prestataire
            p = s.prestatire
            nom_presta = f"{p.prenom} {p.nom}".strip() or "Prestataire"
            note = f"{p.note_moyenne}/5 ({p.nombre_avis} avis)" if p.nombre_avis > 0 else "Pas encore noté"
            niveau = p.niveau.capitalize()
            verifie = "✓ Vérifié" if p.is_verified else "Non vérifié"

            # Disponibilités
            dispos = s.disponibilites.filter(is_available=True)
            if dispos.exists():
                jours = ", ".join(set(d.jour.capitalize() for d in dispos))
                horaires = f"{dispos.first().heure_debut.strftime('%H:%M')}-{dispos.first().heure_fin.strftime('%H:%M')}"
                dispo_label = f"{jours} ({horaires})"
            else:
                dispo_label = "Horaires non précisés"

            context += (
                f"\n📌 SERVICE ID:{s.id}\n"
                f"   Titre        : {s.titre}\n"
                f"   Catégorie    : {s.categorie.nom if s.categorie else 'Non catégorisé'}\n"
                f"   Prix         : {prix_label}\n"
                f"   Localisation : {localisation}\n"
                f"   Disponible   : {dispo_label}\n"
                f"   Prestataire  : {nom_presta} | Niveau: {niveau} | {verifie}\n"
                f"   Note         : {note}\n"
                f"   Description  : {s.description[:150]}{'...' if len(s.description) > 150 else ''}\n"
            )
    else:
        # Pas de services trouvés → donner les catégories dispo
        categories = Category.objects.filter(is_active=True)
        if categories.exists():
            noms = ", ".join([c.nom for c in categories])
            context += f"\n=== CATÉGORIES DISPONIBLES SUR PROXIM ===\n{noms}\n"

        nb_presta = User.objects.filter(
            role=User.ROLE_PRESTATAIRE, is_active=True
        ).count()
        context += f"\nNombre de prestataires actifs : {nb_presta}\n"
        context += "\nAucun service trouvé correspondant à la demande.\n"

    return context


# ── Prompt système ─────────────────────────────────────────────

def get_system_prompt() -> str:
    return """Tu es l'assistant virtuel de Proxim, une marketplace de services au Bénin.

TON RÔLE :
- Aider les clients à trouver des services (électricité, plomberie, ménage, coiffure, etc.)
- Donner des informations PRÉCISES et RÉELLES sur les services disponibles
- Guider les clients pour passer une commande
- Répondre aux questions sur les prix, disponibilités, prestataires

RÈGLES ABSOLUES :
1. Utilise UNIQUEMENT les données fournies dans le contexte [Contexte base de données Proxim]
2. Ne jamais inventer un service, un prix, un prestataire ou une localisation
3. Si un service est trouvé dans le contexte, cite son titre EXACT, son prix EXACT et sa localisation EXACTE
4. Si aucun service n'est trouvé, dis-le honnêtement et propose les catégories disponibles
5. Ne JAMAIS divulguer les contacts (email, téléphone) des prestataires
6. Réponds TOUJOURS en français
7. Sois concis : 3-5 phrases maximum

REDIRECTION VERS LES SERVICES :
- Quand tu mentionnes un service disponible, indique toujours à la fin :
  👉 [VOIR_SERVICE:ID] en remplaçant ID par le SERVICE ID du service concerné
- Exemple : "👉 [VOIR_SERVICE:12]" pour rediriger vers le service #12
- Si plusieurs services correspondent, donne les 2-3 plus pertinents avec leur redirection

COMMENT FONCTIONNE PROXIM :
- Chercher un service → Voir les détails → Commander → Le prestataire accepte/refuse
- Paiement via FedaPay (mobile money ou carte)
- Après service rendu, noter le prestataire

Si on te demande quelque chose hors de ta portée, renvoie vers le support Proxim."""


# ── Fonction principale du chatbot ────────────────────────────

def chat_with_groq(message: str, historique: list) -> str:
    try:
        client = Groq(api_key=settings.GEMINI_API_KEY)

        contexte_db = get_context_from_db(message)

        message_enrichi = message
        if contexte_db:
            message_enrichi = (
                f"{message}\n\n[Contexte base de données Proxim]\n{contexte_db}"
            )

        messages = [
            {"role": "system", "content": get_system_prompt()}
        ]

        for item in historique[-10:]:
            role = item.get('role', 'user')
            if role == 'model':
                role = 'assistant'
            content = item.get('content', '')
            if content:
                messages.append({"role": role, "content": content})

        messages.append({
            "role": "user",
            "content": message_enrichi
        })

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            max_tokens=600,
            temperature=0.3,  # Moins créatif = moins d'hallucinations
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


# Alias pour compatibilité avec l'ancien nom
chat_with_gemini = chat_with_groq