from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date
from .decorators import admin_required

from django.contrib.auth import get_user_model
from accounts.models import ClientProfile, PrestatireProfile, KYCDocument
from services.models import Service, Category
from orders.models import Order
from payments.models import Payment, Withdrawal, Transaction, Wallet
from feed.models import Post, Comment, Like
from messaging.models import Conversation, Message
from notifications.models import Notification
from reports.models import Report
from reviews.models import Review
from reports.models import Report as FeedReport

User = get_user_model()


# ── Auth ──────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated and (request.user.is_staff or request.user.role == 'admin'):
        return redirect('admin_dashboard:home')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user and (user.is_staff or user.role == 'admin'):
            login(request, user)
            return redirect('admin_dashboard:home')
        messages.error(request, 'Email/mot de passe incorrect ou accès non autorisé.')
    return render(request, 'admin_dashboard/login.html')


def logout_view(request):
    logout(request)
    return redirect('/admin-dashboard/login/')


# ── Home ──────────────────────────────────────────────────────

@admin_required
def dashboard_home(request):
    now = timezone.now()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    total_users = User.objects.count()
    total_clients = User.objects.filter(role='client').count()
    total_prestataires = User.objects.filter(role='prestataire').count()
    nouveaux_ce_mois = User.objects.filter(date_joined__gte=debut_mois).count()
    total_services = Service.objects.count()
    services_actifs = Service.objects.filter(is_available=True).count()
    total_commandes = Order.objects.count()
    commandes_ce_mois = Order.objects.filter(date_commande__gte=debut_mois).count()
    commandes_en_attente = Order.objects.filter(statut='EN_NEGOCIATION').count()
    commandes_terminees = Order.objects.filter(statut='TERMINE').count()
    total_paiements = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('montant_total'))['t'] or 0
    revenus_mois = Payment.objects.filter(statut='SUCCES', date_paiement__gte=debut_mois).aggregate(t=Sum('commission_plateforme'))['t'] or 0
    kyc_en_attente = KYCDocument.objects.filter(statut='en_attente').count()
    retraits_en_attente = Withdrawal.objects.filter(statut='EN_ATTENTE').count()
    signalements_en_attente = Report.objects.filter(statut='EN_ATTENTE').count()
    total_posts = Post.objects.count()
    total_conversations = Conversation.objects.count()
    total_avis = Review.objects.count()

    dernieres_commandes = Order.objects.select_related('client', 'prestatire', 'service').order_by('-date_commande')[:8]
    derniers_users = User.objects.order_by('-date_joined')[:6]
    top_services = Service.objects.annotate(nb_commandes=Count('commandes')).order_by('-nb_commandes')[:5]
    derniers_avis = Review.objects.select_related('client', 'prestatire').order_by('-date')[:5]

    context = {
        'total_users': total_users, 'total_clients': total_clients,
        'total_prestataires': total_prestataires, 'nouveaux_ce_mois': nouveaux_ce_mois,
        'total_services': total_services, 'services_actifs': services_actifs,
        'total_commandes': total_commandes, 'commandes_ce_mois': commandes_ce_mois,
        'commandes_en_attente': commandes_en_attente, 'commandes_terminees': commandes_terminees,
        'total_paiements': total_paiements, 'revenus_mois': revenus_mois,
        'kyc_en_attente': kyc_en_attente, 'retraits_en_attente': retraits_en_attente,
        'signalements_en_attente': signalements_en_attente,
        'total_posts': total_posts, 'total_conversations': total_conversations,
        'total_avis': total_avis,
        'dernieres_commandes': dernieres_commandes, 'derniers_users': derniers_users,
        'top_services': top_services, 'derniers_avis': derniers_avis,
        'page': 'home',
    }
    return render(request, 'admin_dashboard/home.html', context)


# ── API Graphes ───────────────────────────────────────────────

@admin_required
def api_stats(request):
    return JsonResponse({
        'users': User.objects.count(),
        'services': Service.objects.count(),
        'commandes': Order.objects.count(),
        'revenus': float(Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('commission_plateforme'))['t'] or 0),
    })


@admin_required
def api_graphe_commandes(request):
    today = date.today()
    data, labels = [], []
    for i in range(11, -1, -1):
        mois = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if mois.month < 12:
            fin = mois.replace(month=mois.month + 1, day=1)
        else:
            fin = mois.replace(year=mois.year + 1, month=1, day=1)
        count = Order.objects.filter(date_commande__date__gte=mois, date_commande__date__lt=fin).count()
        data.append(count)
        labels.append(mois.strftime('%b %Y'))
    return JsonResponse({'labels': labels, 'data': data})


@admin_required
def api_graphe_revenus(request):
    today = date.today()
    data, labels = [], []
    for i in range(11, -1, -1):
        mois = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if mois.month < 12:
            fin = mois.replace(month=mois.month + 1, day=1)
        else:
            fin = mois.replace(year=mois.year + 1, month=1, day=1)
        rev = Payment.objects.filter(statut='SUCCES', date_paiement__date__gte=mois, date_paiement__date__lt=fin).aggregate(t=Sum('commission_plateforme'))['t'] or 0
        data.append(float(rev))
        labels.append(mois.strftime('%b %Y'))
    return JsonResponse({'labels': labels, 'data': data})


# ── Utilisateurs ──────────────────────────────────────────────

@admin_required
def utilisateurs(request):
    role = request.GET.get('role', '')
    statut = request.GET.get('statut', '')
    q = request.GET.get('q', '')
    users = User.objects.annotate(
        nb_commandes=Count('client_profile__commandes', distinct=True)
    ).order_by('-date_joined')
    if role:
        users = users.filter(role=role)
    if statut == 'actif':
        users = users.filter(is_active=True)
    elif statut == 'inactif':
        users = users.filter(is_active=False)
    elif statut == 'non_verifie':
        users = users.filter(is_email_verified=False)
    if q:
        users = users.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))

    stats = {
        'total': User.objects.count(),
        'clients': User.objects.filter(role='client').count(),
        'prestataires': User.objects.filter(role='prestataire').count(),
        'actifs': User.objects.filter(is_active=True).count(),
        'non_verifies': User.objects.filter(is_email_verified=False).count(),
    }
    context = {'users': users, 'total': users.count(), 'role': role, 'statut': statut, 'q': q, 'stats': stats, 'page': 'utilisateurs'}
    return render(request, 'admin_dashboard/utilisateurs.html', context)


@admin_required
def toggle_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            return JsonResponse({'error': 'Vous ne pouvez pas vous désactiver vous-même'}, status=400)
        user.is_active = not user.is_active
        user.save()
        return JsonResponse({'success': True, 'is_active': user.is_active, 'message': f'Utilisateur {"activé" if user.is_active else "désactivé"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def verifier_email_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        user.is_email_verified = True
        user.save()
        return JsonResponse({'success': True, 'message': 'Email vérifié manuellement'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def changer_role_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        nouveau_role = request.POST.get('role')
        if nouveau_role not in ['client', 'prestataire', 'admin']:
            return JsonResponse({'error': 'Rôle invalide'}, status=400)
        user.role = nouveau_role
        if nouveau_role == 'admin':
            user.is_staff = True
        user.save()
        return JsonResponse({'success': True, 'message': f'Rôle changé en {nouveau_role}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            return JsonResponse({'error': 'Impossible de se supprimer soi-même'}, status=400)
        user.delete()
        return JsonResponse({'success': True, 'message': 'Utilisateur supprimé définitivement'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def envoyer_notification_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        titre = request.POST.get('titre', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        if not titre or not contenu:
            return JsonResponse({'error': 'Titre et contenu obligatoires'}, status=400)
        Notification.objects.create(
            destinataire=user, type='NOUVEAU_MESSAGE',
            titre=titre, contenu=contenu
        )
        return JsonResponse({'success': True, 'message': f'Notification envoyée à {user.email}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def detail_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profil = None
    commandes = []
    kycs = []
    avis = []
    services = []
    posts = []
    signalements_recus = Report.objects.filter(cible_user=user).order_by('-date')[:10]
    notifications = Notification.objects.filter(destinataire=user).order_by('-date')[:10]

    if user.role == 'client':
        try:
            profil = user.client_profile
            commandes = Order.objects.filter(client=profil).select_related('service', 'prestatire').order_by('-date_commande')[:10]
            avis = Review.objects.filter(client=profil).select_related('prestatire').order_by('-date')[:5]
        except Exception:
            pass
    elif user.role == 'prestataire':
        try:
            profil = user.prestatire_profile
            commandes = Order.objects.filter(prestatire=profil).select_related('service', 'client').order_by('-date_commande')[:10]
            kycs = KYCDocument.objects.filter(prestatire=profil)
            avis = Review.objects.filter(prestatire=profil).select_related('client').order_by('-date')[:5]
            services = Service.objects.filter(prestatire=profil).annotate(nb_cmd=Count('commandes'))[:8]
            posts = Post.objects.filter(prestatire=profil).order_by('-date_publication')[:5]
        except Exception:
            pass

    try:
        wallet = Wallet.objects.get(user=user)
    except Exception:
        wallet = None

    context = {
        'u': user, 'profil': profil, 'commandes': commandes,
        'kycs': kycs, 'avis': avis, 'services': services, 'posts': posts,
        'wallet': wallet, 'signalements_recus': signalements_recus,
        'notifications': notifications, 'page': 'utilisateurs',
    }
    return render(request, 'admin_dashboard/detail_user.html', context)


# ── Services ──────────────────────────────────────────────────

@admin_required
def services(request):
    q = request.GET.get('q', '')
    categorie_id = request.GET.get('categorie', '')
    statut = request.GET.get('statut', '')
    svcs = Service.objects.select_related('prestatire', 'prestatire__user', 'categorie').annotate(nb_commandes=Count('commandes')).order_by('-date_creation')
    if q:
        svcs = svcs.filter(Q(titre__icontains=q) | Q(prestatire__nom__icontains=q) | Q(prestatire__prenom__icontains=q))
    if categorie_id:
        svcs = svcs.filter(categorie__id=categorie_id)
    if statut == 'actif':
        svcs = svcs.filter(is_available=True)
    elif statut == 'inactif':
        svcs = svcs.filter(is_available=False)
    categories = Category.objects.filter(is_active=True)
    context = {'services': svcs, 'categories': categories, 'total': svcs.count(), 'q': q, 'categorie_id': categorie_id, 'statut': statut, 'page': 'services'}
    return render(request, 'admin_dashboard/services.html', context)


@admin_required
def toggle_service(request, service_id):
    if request.method == 'POST':
        service = get_object_or_404(Service, id=service_id)
        service.is_available = not service.is_available
        service.save()
        return JsonResponse({'success': True, 'is_available': service.is_available, 'message': f'Service {"activé" if service.is_available else "désactivé"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_service(request, service_id):
    if request.method == 'POST':
        service = get_object_or_404(Service, id=service_id)
        service.delete()
        return JsonResponse({'success': True, 'message': 'Service supprimé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Commandes ─────────────────────────────────────────────────

@admin_required
def commandes(request):
    statut = request.GET.get('statut', '')
    q = request.GET.get('q', '')
    cmds = Order.objects.select_related('client', 'prestatire', 'service').order_by('-date_commande')
    if statut:
        cmds = cmds.filter(statut=statut)
    if q:
        cmds = cmds.filter(Q(service__titre__icontains=q) | Q(client__nom__icontains=q) | Q(client__prenom__icontains=q))
    stats = {
        'total': Order.objects.count(),
        'en_nego': Order.objects.filter(statut='EN_NEGOCIATION').count(),
        'accepte': Order.objects.filter(statut='ACCEPTE').count(),
        'en_cours': Order.objects.filter(statut='EN_COURS').count(),
        'termine': Order.objects.filter(statut='TERMINE').count(),
        'annule': Order.objects.filter(statut='ANNULE').count(),
    }
    context = {'commandes': cmds, 'stats': stats, 'statut': statut, 'q': q, 'page': 'commandes'}
    return render(request, 'admin_dashboard/commandes.html', context)


@admin_required
def detail_commande(request, commande_id):
    commande = get_object_or_404(Order.objects.select_related('client', 'prestatire', 'service'), id=commande_id)
    historique = commande.historique_statuts.all().order_by('date')
    negotiations = commande.negotiations.all().order_by('date')
    conversations = commande.conversations.all().prefetch_related('messages')
    try:
        paiement = commande.payment
    except Exception:
        paiement = None
    try:
        review = commande.review
    except Exception:
        review = None
    context = {'commande': commande, 'historique': historique, 'negotiations': negotiations, 'conversations': conversations, 'paiement': paiement, 'review': review, 'page': 'commandes'}
    return render(request, 'admin_dashboard/detail_commande.html', context)


# ── Paiements ─────────────────────────────────────────────────

@admin_required
def paiements(request):
    statut = request.GET.get('statut', '')
    methode = request.GET.get('methode', '')
    pays = Payment.objects.select_related('client', 'order', 'order__service').order_by('-date_paiement')
    if statut:
        pays = pays.filter(statut=statut)
    if methode:
        pays = pays.filter(methode=methode)
    total_succes = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('montant_total'))['t'] or 0
    commission_totale = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('commission_plateforme'))['t'] or 0
    context = {'paiements': pays, 'total_succes': total_succes, 'commission_totale': commission_totale, 'statut': statut, 'methode': methode, 'page': 'paiements'}
    return render(request, 'admin_dashboard/paiements.html', context)


# ── Retraits ──────────────────────────────────────────────────

@admin_required
def retraits(request):
    statut = request.GET.get('statut', '')
    rets = Withdrawal.objects.select_related('prestatire', 'prestatire__user').order_by('-date_demande')
    if statut:
        rets = rets.filter(statut=statut)
    total_en_attente = Withdrawal.objects.filter(statut='EN_ATTENTE').aggregate(t=Sum('montant'))['t'] or 0
    context = {'retraits': rets, 'total_en_attente': total_en_attente, 'statut': statut, 'page': 'retraits'}
    return render(request, 'admin_dashboard/retraits.html', context)


@admin_required
def traiter_retrait(request, retrait_id):
    if request.method == 'POST':
        retrait = get_object_or_404(Withdrawal, id=retrait_id)
        action = request.POST.get('action')
        retrait.statut = 'TRAITE' if action == 'traiter' else 'REJETE'
        retrait.date_traitement = timezone.now()
        retrait.save()
        msg = 'Retrait marqué comme traité' if action == 'traiter' else 'Retrait rejeté'
        # Envoyer notification au prestataire
        try:
            Notification.objects.create(
                destinataire=retrait.prestatire.user,
                type='RETRAIT_TRAITE',
                titre='Demande de retrait',
                contenu=f'Votre demande de retrait de {retrait.montant} FCFA a été {"traitée" if action == "traiter" else "rejetée"}.',
            )
        except Exception:
            pass
        return JsonResponse({'success': True, 'message': msg})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── KYC ───────────────────────────────────────────────────────

@admin_required
def kyc(request):
    statut = request.GET.get('statut', '')
    docs = KYCDocument.objects.select_related('prestatire', 'prestatire__user').order_by('-date_soumission')
    if statut:
        docs = docs.filter(statut=statut)
    stats = {
        'total': KYCDocument.objects.count(),
        'en_attente': KYCDocument.objects.filter(statut='en_attente').count(),
        'valide': KYCDocument.objects.filter(statut='valide').count(),
        'rejete': KYCDocument.objects.filter(statut='rejete').count(),
    }
    context = {'documents': docs, 'stats': stats, 'statut': statut, 'page': 'kyc'}
    return render(request, 'admin_dashboard/kyc.html', context)


@admin_required
def valider_kyc(request, kyc_id):
    if request.method == 'POST':
        doc = get_object_or_404(KYCDocument, id=kyc_id)
        doc.statut = 'valide'
        doc.date_validation = timezone.now()
        doc.save()
        presta = doc.prestatire
        if KYCDocument.objects.filter(prestatire=presta, statut='valide').count() >= 1:
            presta.is_verified = True
            presta.save()
        try:
            Notification.objects.create(
                destinataire=presta.user, type='KYC_VALIDE',
                titre='Document KYC validé',
                contenu=f'Votre document {doc.type_document} a été validé. Votre compte est maintenant vérifié.',
            )
        except Exception:
            pass
        return JsonResponse({'success': True, 'message': 'Document KYC validé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def rejeter_kyc(request, kyc_id):
    if request.method == 'POST':
        doc = get_object_or_404(KYCDocument, id=kyc_id)
        raison = request.POST.get('raison', 'Document non conforme')
        doc.statut = 'rejete'
        doc.date_validation = timezone.now()
        doc.save()
        try:
            Notification.objects.create(
                destinataire=doc.prestatire.user, type='KYC_REJETE',
                titre='Document KYC rejeté',
                contenu=f'Votre document {doc.type_document} a été rejeté. Raison : {raison}',
            )
        except Exception:
            pass
        return JsonResponse({'success': True, 'message': 'Document KYC rejeté'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Catégories ────────────────────────────────────────────────

@admin_required
def categories(request):
    cats = Category.objects.annotate(nb_services=Count('services')).order_by('nom')
    context = {'categories': cats, 'total': cats.count(), 'page': 'categories'}
    return render(request, 'admin_dashboard/categories.html', context)


@admin_required
def creer_categorie(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        if not nom:
            return JsonResponse({'error': 'Le nom est obligatoire'}, status=400)
        cat = Category.objects.create(nom=nom, description=request.POST.get('description', ''), icone=request.POST.get('icone', ''))
        return JsonResponse({'success': True, 'id': cat.id, 'nom': cat.nom, 'message': 'Catégorie créée'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def modifier_categorie(request, cat_id):
    if request.method == 'POST':
        cat = get_object_or_404(Category, id=cat_id)
        nom = request.POST.get('nom', '').strip()
        if nom:
            cat.nom = nom
        cat.description = request.POST.get('description', cat.description)
        cat.icone = request.POST.get('icone', cat.icone)
        cat.save()
        return JsonResponse({'success': True, 'message': 'Catégorie modifiée'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def toggle_categorie(request, cat_id):
    if request.method == 'POST':
        cat = get_object_or_404(Category, id=cat_id)
        cat.is_active = not cat.is_active
        cat.save()
        return JsonResponse({'success': True, 'is_active': cat.is_active, 'message': f'Catégorie {"activée" if cat.is_active else "désactivée"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_categorie(request, cat_id):
    if request.method == 'POST':
        cat = get_object_or_404(Category, id=cat_id)
        if cat.services.count() > 0:
            return JsonResponse({'error': f'Impossible : {cat.services.count()} service(s) utilisent cette catégorie'}, status=400)
        cat.delete()
        return JsonResponse({'success': True, 'message': 'Catégorie supprimée'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Signalements ──────────────────────────────────────────────

@admin_required
def signalements(request):
    statut = request.GET.get('statut', '')
    raison = request.GET.get('raison', '')
    sigs = Report.objects.select_related('reporter', 'cible_user').order_by('-date')
    if statut:
        sigs = sigs.filter(statut=statut)
    if raison:
        sigs = sigs.filter(raison=raison)
    stats = {
        'total': Report.objects.count(),
        'en_attente': Report.objects.filter(statut='EN_ATTENTE').count(),
        'traite': Report.objects.filter(statut='TRAITE').count(),
        'rejete': Report.objects.filter(statut='REJETE').count(),
    }
    context = {'signalements': sigs, 'stats': stats, 'statut': statut, 'raison': raison, 'page': 'signalements'}
    return render(request, 'admin_dashboard/signalements.html', context)


@admin_required
def traiter_signalement(request, sig_id):
    if request.method == 'POST':
        sig = get_object_or_404(Report, id=sig_id)
        action = request.POST.get('action')
        if action == 'traiter':
            sig.statut = 'TRAITE'
            sig.save()
            return JsonResponse({'success': True, 'message': 'Signalement marqué comme traité'})
        elif action == 'rejeter':
            sig.statut = 'REJETE'
            sig.save()
            return JsonResponse({'success': True, 'message': 'Signalement rejeté'})
        elif action == 'suspendre_user':
            sig.cible_user.is_active = False
            sig.cible_user.save()
            sig.statut = 'TRAITE'
            sig.save()
            return JsonResponse({'success': True, 'message': f'Utilisateur {sig.cible_user.email} suspendu'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Avis ──────────────────────────────────────────────────────

@admin_required
def avis(request):
    note_min = request.GET.get('note_min', '')
    q = request.GET.get('q', '')
    all_avis = Review.objects.select_related('client', 'prestatire', 'order__service').order_by('-date')
    if note_min:
        all_avis = all_avis.filter(note__lte=int(note_min))
    if q:
        all_avis = all_avis.filter(
            Q(client__nom__icontains=q) | Q(prestatire__nom__icontains=q) |
            Q(commentaire__icontains=q)
        )
    stats = {
        'total': Review.objects.count(),
        'note_moy': Review.objects.aggregate(m=Avg('note'))['m'] or 0,
        'cinq': Review.objects.filter(note=5).count(),
        'un': Review.objects.filter(note=1).count(),
    }
    context = {'avis': all_avis, 'stats': stats, 'note_min': note_min, 'q': q, 'page': 'avis'}
    return render(request, 'admin_dashboard/avis.html', context)


@admin_required
def supprimer_avis(request, avis_id):
    if request.method == 'POST':
        a = get_object_or_404(Review, id=avis_id)
        a.delete()
        return JsonResponse({'success': True, 'message': 'Avis supprimé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Posts Feed ────────────────────────────────────────────────

@admin_required
def posts(request):
    statut = request.GET.get('statut', '')
    q = request.GET.get('q', '')
    all_posts = Post.objects.select_related('prestatire', 'service').annotate(
        nb_likes=Count('likes', distinct=True),
        nb_comments=Count('commentaires', distinct=True),
    ).order_by('-date_publication')
    if statut == 'actif':
        all_posts = all_posts.filter(is_active=True)
    elif statut == 'inactif':
        all_posts = all_posts.filter(is_active=False)
    if q:
        all_posts = all_posts.filter(Q(contenu__icontains=q) | Q(prestatire__nom__icontains=q))
    context = {'posts': all_posts, 'total': all_posts.count(), 'statut': statut, 'q': q, 'page': 'posts'}
    return render(request, 'admin_dashboard/posts.html', context)


@admin_required
def toggle_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post.is_active = not post.is_active
        post.save()
        return JsonResponse({'success': True, 'is_active': post.is_active, 'message': f'Post {"activé" if post.is_active else "désactivé"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post.delete()
        return JsonResponse({'success': True, 'message': 'Post supprimé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Messagerie ────────────────────────────────────────────────

@admin_required
def messagerie(request):
    convs = Conversation.objects.select_related('client', 'prestatire').annotate(
        nb_messages=Count('messages')
    ).order_by('-dernier_message_date')
    total_messages = Message.objects.count()
    total_non_lus = Message.objects.filter(is_read=False).count()
    context = {
        'conversations': convs, 'total_messages': total_messages,
        'total_non_lus': total_non_lus, 'page': 'messagerie'
    }
    return render(request, 'admin_dashboard/messagerie.html', context)


# ── Notifications broadcast ───────────────────────────────────

@admin_required
def notifications_broadcast(request):
    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        cible = request.POST.get('cible', 'tous')
        if not titre or not contenu:
            return JsonResponse({'error': 'Titre et contenu obligatoires'}, status=400)
        users = User.objects.filter(is_active=True)
        if cible == 'clients':
            users = users.filter(role='client')
        elif cible == 'prestataires':
            users = users.filter(role='prestataire')
        notifs = [
            Notification(destinataire=u, type='NOUVEAU_MESSAGE', titre=titre, contenu=contenu)
            for u in users
        ]
        Notification.objects.bulk_create(notifs)
        return JsonResponse({'success': True, 'message': f'{len(notifs)} notification(s) envoyée(s)'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
