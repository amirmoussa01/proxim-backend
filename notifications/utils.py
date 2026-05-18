from .models import Notification
import os
import json
import firebase_admin
from firebase_admin import credentials, messaging as fcm_messaging
from django.contrib.auth import get_user_model

User = get_user_model()


# ─── FIREBASE ─────────────────────────────────────────────────

def get_firebase_app():
    if not firebase_admin._apps:
        creds_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
        if creds_json:
            try:
                decoded_creds = json.loads(creds_json.strip())
                cred = credentials.Certificate(decoded_creds)
                return firebase_admin.initialize_app(cred)
            except Exception as e:
                print(f"[FCM SETUP ERROR] Erreur initialisation: {e}")
    return firebase_admin.get_app()


def envoyer_push(user, titre, corps, data=None):
    get_firebase_app()
    token = getattr(user, 'fcm_token', None)

    print(f"DEBUG_PUSH_START: Tentative pour {user.email}")

    if not token:
        print(f"DEBUG_PUSH_FAIL: Pas de token pour {user.email}")
        return

    payload_data = {k: str(v) for k, v in (data or {}).items()}

    try:
        message = fcm_messaging.Message(
            notification=fcm_messaging.Notification(
                title=titre,
                body=corps,
            ),
            android=fcm_messaging.AndroidConfig(
                notification=fcm_messaging.AndroidNotification(
                    click_action='FLUTTER_NOTIFICATION_CLICK',
                    channel_id='proxim_channel',
                ),
            ),
            data=payload_data,
            token=token,
        )
        response = fcm_messaging.send(message)
        print(f'[FCM SUCCESS] Message envoye avec succes ! ID: {response}')
    except Exception as e:
        print(f'[FCM ERROR] Erreur lors de l\'envoi Firebase: {str(e)}')


def notifier(destinataire, type_notif, titre, contenu, objet_id=None, objet_type=None):
    Notification.objects.create(
        destinataire=destinataire,
        type=type_notif,
        titre=titre,
        contenu=contenu,
        lien_objet_id=objet_id,
        lien_objet_type=objet_type,
    )
    data_payload = {
        'type': type_notif,
        'objet_id': str(objet_id) if objet_id else '',
        'objet_type': str(objet_type) if objet_type else '',
    }
    envoyer_push(destinataire, titre, contenu, data=data_payload)


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
    # 1. Notifier le client
    notifier(
        destinataire=order.client.user,
        type_notif='COMMANDE_TERMINEE',
        titre='Commande terminee',
        contenu=f'Votre commande pour "{order.service.titre}" est terminee. Laissez un avis !',
        objet_id=order.id,
        objet_type='order',
    )
    # 2. Notifier TOUS les admins pour qu'ils puissent valider et declencher le virement
    admins = User.objects.filter(is_staff=True, is_active=True)
    for admin in admins:
        notifier(
            destinataire=admin,
            type_notif='FIN_SERVICE_A_VALIDER',
            titre='Service termine — Validation requise',
            contenu=(
                f'La commande #{order.id} ({order.service.titre}) est marquee comme terminee '
                f'par {order.prestatire.prenom} {order.prestatire.nom}. '
                f'Veuillez valider pour declencher le virement de '
                f'{order.payment.montant_prestatire if hasattr(order, "payment") else "—"} FCFA.'
            ),
            objet_id=order.id,
            objet_type='order',
        )


def notif_commande_annulee(order, annule_par):
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
    """Notifie le prestataire que les fonds sont bien bloques (en escrow)."""
    notifier(
        destinataire=payment.order.prestatire.user,
        type_notif='PAIEMENT_RECU',
        titre='Paiement recu — en attente de validation',
        contenu=(
            f'Le client a paye {payment.montant_total} FCFA pour la commande #{payment.order.id}. '
            f'Votre part ({payment.montant_prestatire} FCFA) sera versee apres validation de la fin du service.'
        ),
        objet_id=payment.id,
        objet_type='payment',
    )


def notif_virement_effectue(payment):
    """Notifie le prestataire que l'admin a valide et que le virement est effectue."""
    notifier(
        destinataire=payment.order.prestatire.user,
        type_notif='VIREMENT_EFFECTUE',
        titre='Virement effectue',
        contenu=(
            f'L\'admin a valide la fin du service pour la commande #{payment.order.id}. '
            f'{payment.montant_prestatire} FCFA ont ete credites sur votre portefeuille.'
        ),
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
    prenom = review.client.user.prenom if hasattr(review.client, 'user') else ''
    nom = review.client.user.nom if hasattr(review.client, 'user') else ''
    notifier(
        destinataire=review.prestatire.user,
        type_notif='NOUVEL_AVIS',
        titre='Nouvel avis',
        contenu=f'{prenom} {nom} vous a laisse un avis {review.note}/5',
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