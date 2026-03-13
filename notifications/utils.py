from .models import Notification


def notifier(destinataire, type_notif, titre, contenu, objet_id=None, objet_type=None):
    Notification.objects.create(
        destinataire=destinataire,
        type=type_notif,
        titre=titre,
        contenu=contenu,
        lien_objet_id=objet_id,
        lien_objet_type=objet_type,
    )


# ─── COMMANDES ────────────────────────────────────────────────

def notif_commande_recue(order):
    notifier(
        destinataire=order.prestatire.user,
        type_notif='COMMANDE_RECUE',
        titre='Nouvelle commande',
        contenu=f'{order.client.prenom} {order.client.nom} vous a envoye une commande pour "{order.service.titre}"',
        objet_id=order.id,
        objet_type='order',
    )


def notif_commande_acceptee(order):
    notifier(
        destinataire=order.client.user,
        type_notif='COMMANDE_ACCEPTEE',
        titre='Commande acceptee',
        contenu=f'Votre commande pour "{order.service.titre}" a ete acceptee par {order.prestatire.prenom} {order.prestatire.nom}',
        objet_id=order.id,
        objet_type='order',
    )


def notif_commande_terminee(order):
    notifier(
        destinataire=order.client.user,
        type_notif='COMMANDE_TERMINEE',
        titre='Commande terminee',
        contenu=f'Votre commande pour "{order.service.titre}" est terminee. Laissez un avis !',
        objet_id=order.id,
        objet_type='order',
    )


def notif_commande_annulee(order, annule_par):
    # Notifier l'autre partie
    if annule_par == order.client.user:
        destinataire = order.prestatire.user
        message = f'La commande pour "{order.service.titre}" a ete annulee par le client'
    else:
        destinataire = order.client.user
        message = f'La commande pour "{order.service.titre}" a ete annulee par le prestataire'

    notifier(
        destinataire=destinataire,
        type_notif='COMMANDE_ANNULEE',
        titre='Commande annulee',
        contenu=message,
        objet_id=order.id,
        objet_type='order',
    )


def notif_nouveau_statut(order, nouveau_statut):
    notifier(
        destinataire=order.client.user,
        type_notif='NOUVEAU_STATUT',
        titre='Statut commande mis a jour',
        contenu=f'Votre commande pour "{order.service.titre}" est maintenant : {nouveau_statut}',
        objet_id=order.id,
        objet_type='order',
    )


# ─── NEGOCIATION ──────────────────────────────────────────────

def notif_nouvelle_negociation(negotiation):
    order = negotiation.order
    expediteur = negotiation.expediteur

    if expediteur == order.client.user:
        destinataire = order.prestatire.user
        message = f'{order.client.prenom} vous a envoye une proposition pour "{order.service.titre}"'
    else:
        destinataire = order.client.user
        message = f'{order.prestatire.prenom} vous a envoye une proposition pour "{order.service.titre}"'

    notifier(
        destinataire=destinataire,
        type_notif='COMMANDE_RECUE',
        titre='Nouvelle proposition de negociation',
        contenu=message,
        objet_id=order.id,
        objet_type='order',
    )


# ─── MESSAGES ─────────────────────────────────────────────────

def notif_nouveau_message(message):
    conversation = message.conversation
    expediteur = message.expediteur

    if expediteur == conversation.client.user:
        destinataire = conversation.prestatire.user
        # ← utilise user.prenom / user.nom
        nom_expediteur = f'{conversation.client.user.prenom} {conversation.client.user.nom}'
    else:
        destinataire = conversation.client.user
        nom_expediteur = f'{conversation.prestatire.user.prenom} {conversation.prestatire.user.nom}'

    notifier(
        destinataire=destinataire,
        type_notif='NOUVEAU_MESSAGE',
        titre=f'Nouveau message de {nom_expediteur}',
        contenu=message.contenu[:100] if message.contenu else 'Image',
        objet_id=conversation.id,
        objet_type='conversation',
    )

# ─── PAIEMENTS ────────────────────────────────────────────────

def notif_paiement_recu(payment):
    notifier(
        destinataire=payment.order.prestatire.user,
        type_notif='PAIEMENT_RECU',
        titre='Paiement recu',
        contenu=f'Vous avez recu un paiement de {payment.montant_prestatire} FCFA pour la commande #{payment.order.id}',
        objet_id=payment.id,
        objet_type='payment',
    )


def notif_retrait_traite(retrait):
    notifier(
        destinataire=retrait.prestatire.user,
        type_notif='RETRAIT_TRAITE',
        titre='Retrait traite',
        contenu=f'Votre retrait de {retrait.montant} FCFA a ete traite avec succes',
        objet_id=retrait.id,
        objet_type='withdrawal',
    )


# ─── AVIS ─────────────────────────────────────────────────────

def notif_nouvel_avis(review):
    notifier(
        destinataire=review.prestatire.user,
        type_notif='NOUVEL_AVIS',
        titre='Nouvel avis',
        contenu=f'{review.client.prenom} {review.client.nom} vous a laisse un avis {review.note}/5',
        objet_id=review.id,
        objet_type='review',
    )


# ─── KYC ──────────────────────────────────────────────────────

def notif_kyc_valide(prestatire):
    notifier(
        destinataire=prestatire.user,
        type_notif='KYC_VALIDE',
        titre='Profil verifie',
        contenu='Votre profil a ete verifie avec succes. Vous etes maintenant un prestataire certifie !',
        objet_id=prestatire.id,
        objet_type='prestatire',
    )


def notif_kyc_rejete(prestatire):
    notifier(
        destinataire=prestatire.user,
        type_notif='KYC_REJETE',
        titre='Verification refusee',
        contenu='Votre demande de verification a ete refusee. Veuillez soumettre de nouveaux documents.',
        objet_id=prestatire.id,
        objet_type='prestatire',
    )