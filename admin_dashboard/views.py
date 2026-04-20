from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date
import json
from .decorators import admin_required

from django.contrib.auth import get_user_model
from accounts.models import ClientProfile, PrestatireProfile, KYCDocument
from services.models import Service, Category
from orders.models import Order
from payments.models import Payment, Withdrawal, Transaction, Wallet

User = get_user_model()


# ── Authentification ──────────────────────────────────────────

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


# ── Home / Vue générale ───────────────────────────────────────

@admin_required
def dashboard_home(request):
    now = timezone.now()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    debut_semaine = now - timedelta(days=7)

    # Stats globales
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

    total_paiements = Payment.objects.filter(statut='SUCCES').aggregate(
        total=Sum('montant_total'))['total'] or 0
    revenus_mois = Payment.objects.filter(
        statut='SUCCES', date_paiement__gte=debut_mois
    ).aggregate(total=Sum('commission_plateforme'))['total'] or 0

    kyc_en_attente = KYCDocument.objects.filter(statut='en_attente').count()
    retraits_en_attente = Withdrawal.objects.filter(statut='EN_ATTENTE').count()

    # Dernières commandes
    dernieres_commandes = Order.objects.select_related(
        'client', 'prestatire', 'service'
    ).order_by('-date_commande')[:8]

    # Derniers utilisateurs
    derniers_users = User.objects.order_by('-date_joined')[:6]

    # Services les plus commandés
    top_services = Service.objects.annotate(
        nb_commandes=Count('commandes')
    ).order_by('-nb_commandes')[:5]

    context = {
        'total_users': total_users,
        'total_clients': total_clients,
        'total_prestataires': total_prestataires,
        'nouveaux_ce_mois': nouveaux_ce_mois,
        'total_services': total_services,
        'services_actifs': services_actifs,
        'total_commandes': total_commandes,
        'commandes_ce_mois': commandes_ce_mois,
        'commandes_en_attente': commandes_en_attente,
        'commandes_terminees': commandes_terminees,
        'total_paiements': total_paiements,
        'revenus_mois': revenus_mois,
        'kyc_en_attente': kyc_en_attente,
        'retraits_en_attente': retraits_en_attente,
        'dernieres_commandes': dernieres_commandes,
        'derniers_users': derniers_users,
        'top_services': top_services,
        'page': 'home',
    }
    return render(request, 'admin_dashboard/home.html', context)


# ── API Stats pour graphes ────────────────────────────────────

@admin_required
def api_stats(request):
    now = timezone.now()
    stats = {
        'users': User.objects.count(),
        'services': Service.objects.count(),
        'commandes': Order.objects.count(),
        'revenus': float(Payment.objects.filter(statut='SUCCES').aggregate(
            t=Sum('commission_plateforme'))['t'] or 0),
    }
    return JsonResponse(stats)


@admin_required
def api_graphe_commandes(request):
    today = date.today()
    data = []
    labels = []
    for i in range(11, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 30)
        mois = d.replace(day=1)
        fin_mois = (mois.replace(month=mois.month % 12 + 1, day=1)
                    if mois.month < 12 else mois.replace(year=mois.year + 1, month=1, day=1))
        count = Order.objects.filter(
            date_commande__date__gte=mois,
            date_commande__date__lt=fin_mois
        ).count()
        data.append(count)
        labels.append(mois.strftime('%b %Y'))
    return JsonResponse({'labels': labels, 'data': data})


@admin_required
def api_graphe_revenus(request):
    today = date.today()
    data = []
    labels = []
    for i in range(11, -1, -1):
        d = today.replace(day=1) - timedelta(days=i * 30)
        mois = d.replace(day=1)
        fin_mois = (mois.replace(month=mois.month % 12 + 1, day=1)
                    if mois.month < 12 else mois.replace(year=mois.year + 1, month=1, day=1))
        revenu = Payment.objects.filter(
            statut='SUCCES',
            date_paiement__date__gte=mois,
            date_paiement__date__lt=fin_mois
        ).aggregate(t=Sum('commission_plateforme'))['t'] or 0
        data.append(float(revenu))
        labels.append(mois.strftime('%b %Y'))
    return JsonResponse({'labels': labels, 'data': data})


# ── Utilisateurs ──────────────────────────────────────────────

@admin_required
def utilisateurs(request):
    role = request.GET.get('role', '')
    statut = request.GET.get('statut', '')
    q = request.GET.get('q', '')

    users = User.objects.all().order_by('-date_joined')

    if role:
        users = users.filter(role=role)
    if statut == 'actif':
        users = users.filter(is_active=True)
    elif statut == 'inactif':
        users = users.filter(is_active=False)
    if q:
        users = users.filter(
            Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    context = {
        'users': users,
        'total': users.count(),
        'role': role,
        'statut': statut,
        'q': q,
        'page': 'utilisateurs',
    }
    return render(request, 'admin_dashboard/utilisateurs.html', context)


@admin_required
def toggle_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        if user == request.user:
            return JsonResponse({'error': 'Vous ne pouvez pas vous désactiver vous-même'}, status=400)
        user.is_active = not user.is_active
        user.save()
        return JsonResponse({
            'success': True,
            'is_active': user.is_active,
            'message': f'Utilisateur {"activé" if user.is_active else "désactivé"}'
        })
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def detail_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profil = None
    commandes = []
    kycs = []

    if user.role == 'client':
        try:
            profil = user.client_profile
            commandes = Order.objects.filter(client=profil).order_by('-date_commande')[:10]
        except Exception:
            pass
    elif user.role == 'prestataire':
        try:
            profil = user.prestatire_profile
            commandes = Order.objects.filter(prestatire=profil).order_by('-date_commande')[:10]
            kycs = KYCDocument.objects.filter(prestatire=profil)
        except Exception:
            pass

    context = {
        'u': user,
        'profil': profil,
        'commandes': commandes,
        'kycs': kycs,
        'page': 'utilisateurs',
    }
    return render(request, 'admin_dashboard/detail_user.html', context)


# ── Services ──────────────────────────────────────────────────

@admin_required
def services(request):
    q = request.GET.get('q', '')
    categorie_id = request.GET.get('categorie', '')
    statut = request.GET.get('statut', '')

    svcs = Service.objects.select_related(
        'prestatire', 'prestatire__user', 'categorie'
    ).annotate(nb_commandes=Count('commandes')).order_by('-date_creation')

    if q:
        svcs = svcs.filter(
            Q(titre__icontains=q) | Q(prestatire__nom__icontains=q) |
            Q(prestatire__prenom__icontains=q)
        )
    if categorie_id:
        svcs = svcs.filter(categorie__id=categorie_id)
    if statut == 'actif':
        svcs = svcs.filter(is_available=True)
    elif statut == 'inactif':
        svcs = svcs.filter(is_available=False)

    categories = Category.objects.filter(is_active=True)

    context = {
        'services': svcs,
        'categories': categories,
        'total': svcs.count(),
        'q': q,
        'categorie_id': categorie_id,
        'statut': statut,
        'page': 'services',
    }
    return render(request, 'admin_dashboard/services.html', context)


@admin_required
def toggle_service(request, service_id):
    if request.method == 'POST':
        service = get_object_or_404(Service, id=service_id)
        service.is_available = not service.is_available
        service.save()
        return JsonResponse({
            'success': True,
            'is_available': service.is_available,
            'message': f'Service {"activé" if service.is_available else "désactivé"}'
        })
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

    cmds = Order.objects.select_related(
        'client', 'prestatire', 'service'
    ).order_by('-date_commande')

    if statut:
        cmds = cmds.filter(statut=statut)
    if q:
        cmds = cmds.filter(
            Q(service__titre__icontains=q) |
            Q(client__nom__icontains=q) |
            Q(client__prenom__icontains=q)
        )

    stats = {
        'total': Order.objects.count(),
        'en_nego': Order.objects.filter(statut='EN_NEGOCIATION').count(),
        'accepte': Order.objects.filter(statut='ACCEPTE').count(),
        'en_cours': Order.objects.filter(statut='EN_COURS').count(),
        'termine': Order.objects.filter(statut='TERMINE').count(),
        'annule': Order.objects.filter(statut='ANNULE').count(),
    }

    context = {
        'commandes': cmds,
        'stats': stats,
        'statut': statut,
        'q': q,
        'page': 'commandes',
    }
    return render(request, 'admin_dashboard/commandes.html', context)


@admin_required
def detail_commande(request, commande_id):
    commande = get_object_or_404(
        Order.objects.select_related('client', 'prestatire', 'service'), id=commande_id
    )
    historique = commande.historique_statuts.all().order_by('date')
    negotiations = commande.negotiations.all().order_by('date')
    try:
        paiement = commande.payment
    except Exception:
        paiement = None

    context = {
        'commande': commande,
        'historique': historique,
        'negotiations': negotiations,
        'paiement': paiement,
        'page': 'commandes',
    }
    return render(request, 'admin_dashboard/detail_commande.html', context)


# ── Paiements ─────────────────────────────────────────────────

@admin_required
def paiements(request):
    statut = request.GET.get('statut', '')
    methode = request.GET.get('methode', '')

    pays = Payment.objects.select_related(
        'client', 'order', 'order__service'
    ).order_by('-date_paiement')

    if statut:
        pays = pays.filter(statut=statut)
    if methode:
        pays = pays.filter(methode=methode)

    total_succes = Payment.objects.filter(statut='SUCCES').aggregate(
        t=Sum('montant_total'))['t'] or 0
    commission_totale = Payment.objects.filter(statut='SUCCES').aggregate(
        t=Sum('commission_plateforme'))['t'] or 0

    context = {
        'paiements': pays,
        'total_succes': total_succes,
        'commission_totale': commission_totale,
        'statut': statut,
        'methode': methode,
        'page': 'paiements',
    }
    return render(request, 'admin_dashboard/paiements.html', context)


# ── Retraits ──────────────────────────────────────────────────

@admin_required
def retraits(request):
    statut = request.GET.get('statut', '')

    rets = Withdrawal.objects.select_related(
        'prestatire', 'prestatire__user'
    ).order_by('-date_demande')

    if statut:
        rets = rets.filter(statut=statut)

    total_en_attente = Withdrawal.objects.filter(statut='EN_ATTENTE').aggregate(
        t=Sum('montant'))['t'] or 0

    context = {
        'retraits': rets,
        'total_en_attente': total_en_attente,
        'statut': statut,
        'page': 'retraits',
    }
    return render(request, 'admin_dashboard/retraits.html', context)


@admin_required
def traiter_retrait(request, retrait_id):
    if request.method == 'POST':
        retrait = get_object_or_404(Withdrawal, id=retrait_id)
        action = request.POST.get('action')
        if action == 'traiter':
            retrait.statut = 'TRAITE'
            retrait.date_traitement = timezone.now()
            retrait.save()
            return JsonResponse({'success': True, 'message': 'Retrait marqué comme traité'})
        elif action == 'rejeter':
            retrait.statut = 'REJETE'
            retrait.date_traitement = timezone.now()
            retrait.save()
            return JsonResponse({'success': True, 'message': 'Retrait rejeté'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── KYC ───────────────────────────────────────────────────────

@admin_required
def kyc(request):
    statut = request.GET.get('statut', '')

    docs = KYCDocument.objects.select_related(
        'prestatire', 'prestatire__user'
    ).order_by('-date_soumission')

    if statut:
        docs = docs.filter(statut=statut)

    stats = {
        'total': KYCDocument.objects.count(),
        'en_attente': KYCDocument.objects.filter(statut='en_attente').count(),
        'valide': KYCDocument.objects.filter(statut='valide').count(),
        'rejete': KYCDocument.objects.filter(statut='rejete').count(),
    }

    context = {
        'documents': docs,
        'stats': stats,
        'statut': statut,
        'page': 'kyc',
    }
    return render(request, 'admin_dashboard/kyc.html', context)


@admin_required
def valider_kyc(request, kyc_id):
    if request.method == 'POST':
        doc = get_object_or_404(KYCDocument, id=kyc_id)
        doc.statut = 'valide'
        doc.date_validation = timezone.now()
        doc.save()
        # Vérifier si le prestataire a assez de docs validés
        presta = doc.prestatire
        docs_valides = KYCDocument.objects.filter(prestatire=presta, statut='valide').count()
        if docs_valides >= 1:
            presta.is_verified = True
            presta.save()
        return JsonResponse({'success': True, 'message': 'Document KYC validé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def rejeter_kyc(request, kyc_id):
    if request.method == 'POST':
        doc = get_object_or_404(KYCDocument, id=kyc_id)
        doc.statut = 'rejete'
        doc.date_validation = timezone.now()
        doc.save()
        return JsonResponse({'success': True, 'message': 'Document KYC rejeté'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Catégories ────────────────────────────────────────────────

@admin_required
def categories(request):
    cats = Category.objects.annotate(nb_services=Count('services')).order_by('nom')
    context = {
        'categories': cats,
        'total': cats.count(),
        'page': 'categories',
    }
    return render(request, 'admin_dashboard/categories.html', context)


@admin_required
def creer_categorie(request):
    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        icone = request.POST.get('icone', '').strip()
        if not nom:
            return JsonResponse({'error': 'Le nom est obligatoire'}, status=400)
        cat = Category.objects.create(nom=nom, description=description, icone=icone)
        return JsonResponse({
            'success': True,
            'id': cat.id,
            'nom': cat.nom,
            'message': 'Catégorie créée'
        })
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def toggle_categorie(request, cat_id):
    if request.method == 'POST':
        cat = get_object_or_404(Category, id=cat_id)
        cat.is_active = not cat.is_active
        cat.save()
        return JsonResponse({
            'success': True,
            'is_active': cat.is_active,
            'message': f'Catégorie {"activée" if cat.is_active else "désactivée"}'
        })
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_categorie(request, cat_id):
    if request.method == 'POST':
        cat = get_object_or_404(Category, id=cat_id)
        if cat.services.count() > 0:
            return JsonResponse({
                'error': f'Impossible : {cat.services.count()} service(s) utilisent cette catégorie'
            }, status=400)
        cat.delete()
        return JsonResponse({'success': True, 'message': 'Catégorie supprimée'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)
