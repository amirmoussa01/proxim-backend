from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date
from io import BytesIO
from .decorators import admin_required
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.platypus import KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas

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


# ── Helpers contexte global ───────────────────────────────────

def _global_ctx():
    return {
        'kyc_en_attente': KYCDocument.objects.filter(statut='en_attente').count(),
        'retraits_en_attente': Withdrawal.objects.filter(statut='EN_ATTENTE').count(),
        'signalements_en_attente': Report.objects.filter(statut='EN_ATTENTE').count(),
        'commandes_en_attente': Order.objects.filter(statut='EN_NEGOCIATION').count(),
        # ← badge sidebar : commandes TERMINE avec fonds encore bloques
        'virements_a_valider': Payment.objects.filter(
            statut='SUCCES',
            fonds_bloques=True,
            order__statut='TERMINE',
        ).count(),
    }


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
    total_avis = Review.objects.count()
    virements_a_valider = Payment.objects.filter(
        statut='SUCCES', fonds_bloques=True, order__statut='TERMINE'
    ).count()

    dernieres_commandes = Order.objects.select_related('client', 'prestatire', 'service').order_by('-date_commande')[:8]
    top_services = Service.objects.annotate(nb_commandes=Count('commandes')).order_by('-nb_commandes')[:5]
    derniers_avis = Review.objects.select_related('client', 'prestatire').order_by('-date')[:5]

    ctx = {
        'total_users': total_users, 'total_clients': total_clients,
        'total_prestataires': total_prestataires, 'nouveaux_ce_mois': nouveaux_ce_mois,
        'total_services': total_services, 'services_actifs': services_actifs,
        'total_commandes': total_commandes, 'commandes_ce_mois': commandes_ce_mois,
        'commandes_en_attente': commandes_en_attente, 'commandes_terminees': commandes_terminees,
        'total_paiements': total_paiements, 'revenus_mois': revenus_mois,
        'kyc_en_attente': kyc_en_attente, 'retraits_en_attente': retraits_en_attente,
        'signalements_en_attente': signalements_en_attente,
        'total_posts': total_posts, 'total_avis': total_avis,
        'virements_a_valider': virements_a_valider,
        'dernieres_commandes': dernieres_commandes,
        'top_services': top_services, 'derniers_avis': derniers_avis,
        'page': 'home',
    }
    return render(request, 'admin_dashboard/home.html', ctx)


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
        fin = mois.replace(month=mois.month % 12 + 1, day=1) if mois.month < 12 else mois.replace(year=mois.year + 1, month=1, day=1)
        data.append(Order.objects.filter(date_commande__date__gte=mois, date_commande__date__lt=fin).count())
        labels.append(mois.strftime('%b %Y'))
    return JsonResponse({'labels': labels, 'data': data})


@admin_required
def api_graphe_revenus(request):
    today = date.today()
    data, labels = [], []
    for i in range(11, -1, -1):
        mois = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        fin = mois.replace(month=mois.month % 12 + 1, day=1) if mois.month < 12 else mois.replace(year=mois.year + 1, month=1, day=1)
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
    users = User.objects.order_by('-date_joined')
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
    ctx = {'users': users, 'total': users.count(), 'role': role, 'statut': statut, 'q': q, 'stats': stats, 'page': 'utilisateurs'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/utilisateurs.html', ctx)


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
def changer_niveau_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        niveau = request.POST.get('niveau')
        if niveau not in ['bronze', 'argent', 'or', 'expert']:
            return JsonResponse({'error': 'Niveau invalide'}, status=400)
        try:
            profil = user.prestatire_profile
            profil.niveau = niveau
            profil.save()
            return JsonResponse({'success': True, 'message': f'Niveau changé en {niveau.upper()}'})
        except Exception:
            return JsonResponse({'error': 'Profil prestataire introuvable'}, status=404)
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def modifier_profil_user(request, user_id):
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        try:
            if user.role == 'client':
                profil = user.client_profile
                profil.nom = request.POST.get('nom', profil.nom)
                profil.prenom = request.POST.get('prenom', profil.prenom)
                profil.adresse = request.POST.get('adresse', profil.adresse)
                profil.save()
            elif user.role == 'prestataire':
                profil = user.prestatire_profile
                profil.nom = request.POST.get('nom', profil.nom)
                profil.prenom = request.POST.get('prenom', profil.prenom)
                profil.adresse = request.POST.get('adresse', profil.adresse)
                profil.bio = request.POST.get('bio', profil.bio)
                profil.save()
            phone = request.POST.get('phone', '').strip()
            if phone:
                user.phone = phone
                user.save()
            return JsonResponse({'success': True, 'message': 'Profil modifié avec succès'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
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
        Notification.objects.create(destinataire=user, type='NOUVEAU_MESSAGE', titre=titre, contenu=contenu)
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
    niveaux = ["bronze", "argent", "or", "expert"]
    tabs = [
        ("commandes", "Commandes", "shopping-cart"),
        ("services", "Services", "briefcase"),
        ("kycs", "KYC", "id-card"),
        ("avis", "Avis", "star"),
        ("posts", "Posts", "photo-video"),
        ("signalements", "Signalements", "flag"),
        ("notifications", "Notifications", "bell"),
    ]
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
        transactions = wallet.transactions.order_by('-date')[:10]
    except Exception:
        wallet = None
        transactions = []

    ctx = {
        'u': user, 'profil': profil, 'commandes': commandes, 'kycs': kycs,
        'avis': avis, 'services': services, 'posts': posts,
        'wallet': wallet, 'transactions': transactions,
        'signalements_recus': signalements_recus, 'notifications': notifications,
        'niveaux': niveaux, 'tabs': tabs, 'page': 'utilisateurs',
    }
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/detail_user.html', ctx)


# ── Couleurs Proxim ───────────────────────────────────────────

_DARK_BLUE  = colors.HexColor('#0D1B2A')
_GOLD       = colors.HexColor('#F4A922')
_GOLD_LIGHT = colors.HexColor('#FDE9B8')
_LIGHT_GRAY = colors.HexColor('#F4F6F9')
_MID_GRAY   = colors.HexColor('#DDE2EA')
_TEXT_DARK  = colors.HexColor('#1A1A2E')
_TEXT_GRAY  = colors.HexColor('#6B7280')
_GREEN      = colors.HexColor('#059669')
_WHITE      = colors.white


def _proxim_page_chrome(c, doc, ref_doc, now_str, generated):
    W, H = A4
    MARGIN_H = 18 * mm
    c.saveState()

    header_h = 40 * mm
    c.setFillColor(_DARK_BLUE)
    c.rect(0, H - header_h, W, header_h, fill=1, stroke=0)
    c.setFillColor(_GOLD)
    c.rect(0, H - header_h, 4, header_h, fill=1, stroke=0)
    c.setFillColor(_GOLD)
    c.rect(0, H - header_h, W, 2, fill=1, stroke=0)

    logo_x, logo_y = 14 * mm, H - 18 * mm
    c.setFillColor(_WHITE)
    c.setFont('Helvetica-Bold', 22)
    c.drawString(logo_x, logo_y, 'Proxim')
    offset = c.stringWidth('Proxim', 'Helvetica-Bold', 22)
    c.setFillColor(_GOLD)
    c.drawString(logo_x + offset, logo_y, '.')
    c.setFillColor(colors.HexColor('#8FA5BC'))
    c.setFont('Helvetica', 7.5)
    c.drawString(logo_x, logo_y - 10, 'Plateforme de services a domicile')

    badge_w, badge_h = 58 * mm, 7 * mm
    badge_x = W - MARGIN_H - badge_w
    badge_y = H - 10 * mm
    c.setFillColor(_GOLD)
    c.roundRect(badge_x, badge_y - badge_h, badge_w, badge_h, 3, fill=1, stroke=0)
    c.setFillColor(_DARK_BLUE)
    c.setFont('Helvetica-Bold', 6.5)
    c.drawCentredString(badge_x + badge_w / 2, badge_y - badge_h + 2, 'DOCUMENT ADMINISTRATIF CONFIDENTIEL')

    c.setFillColor(_WHITE)
    c.setFont('Helvetica-Bold', 9)
    c.drawRightString(W - MARGIN_H, H - 23 * mm, f'Ref. : {ref_doc}')
    c.setFillColor(colors.HexColor('#8FA5BC'))
    c.setFont('Helvetica', 7.5)
    c.drawRightString(W - MARGIN_H, H - 31 * mm, f'Genere le {now_str}')

    c.setStrokeColor(colors.HexColor('#2A4A6A'))
    c.setLineWidth(0.5)
    c.line(W / 2, H - header_h + 6, W / 2, H - 6)

    fy = 14 * mm
    c.setStrokeColor(_MID_GRAY)
    c.setLineWidth(0.5)
    c.line(MARGIN_H, fy + 2, W - MARGIN_H, fy + 2)
    c.setFillColor(_DARK_BLUE)
    c.rect(MARGIN_H, fy, W - 2 * MARGIN_H, 2, fill=1, stroke=0)
    c.setFillColor(_TEXT_GRAY)
    c.setFont('Helvetica', 7)
    c.drawString(MARGIN_H, fy - 7, f'Proxim Admin  •  {ref_doc}  •  Confidentiel')
    c.setFillColor(_DARK_BLUE)
    c.setFont('Helvetica-Bold', 7.5)
    c.drawCentredString(W / 2, fy - 7, f'Page {doc.page}')
    c.setFillColor(_TEXT_GRAY)
    c.setFont('Helvetica', 7)
    c.drawRightString(W - MARGIN_H, fy - 7, f'Genere le {generated}')

    c.restoreState()


@admin_required
def exporter_user_pdf(request, user_id):
    user = get_object_or_404(User, id=user_id)
    profil = None
    commandes = []
    avis = []
    wallet = None

    if user.role == 'client':
        try:
            profil = user.client_profile
            commandes = list(Order.objects.filter(client=profil).select_related('service').order_by('-date_commande')[:20])
            avis = list(Review.objects.filter(client=profil).order_by('-date')[:10])
        except Exception:
            pass
    elif user.role == 'prestataire':
        try:
            profil = user.prestatire_profile
            commandes = list(Order.objects.filter(prestatire=profil).select_related('service').order_by('-date_commande')[:20])
            avis = list(Review.objects.filter(prestatire=profil).order_by('-date')[:10])
        except Exception:
            pass

    try:
        wallet = Wallet.objects.get(user=user)
    except Exception:
        pass

    now      = timezone.now()
    now_str  = now.strftime('%d/%m/%Y a %H:%M')
    gen_date = now.strftime('%d/%m/%Y')
    ref_doc  = f'PRX-USR-{user.id:05d}'

    PAGE_W, PAGE_H = A4
    MARGIN_H   = 18 * mm
    CONTENT_W  = PAGE_W - 2 * MARGIN_H

    ST = {
        'main_title': ParagraphStyle('MT', fontName='Helvetica-Bold', fontSize=16, textColor=_DARK_BLUE, spaceAfter=0),
        'id_right':   ParagraphStyle('IR', fontName='Helvetica', fontSize=10, textColor=_TEXT_GRAY, alignment=TA_RIGHT, spaceAfter=0),
        'section':    ParagraphStyle('SEC', fontName='Helvetica-Bold', fontSize=8, textColor=_WHITE, spaceAfter=0),
        'label':      ParagraphStyle('LBL', fontName='Helvetica', fontSize=7.5, textColor=_TEXT_GRAY, spaceAfter=1),
        'value':      ParagraphStyle('VAL', fontName='Helvetica-Bold', fontSize=10.5, textColor=_TEXT_DARK, spaceAfter=0, leading=13),
        'value_green':ParagraphStyle('VGN', fontName='Helvetica-Bold', fontSize=14, textColor=_GREEN, spaceAfter=0),
        'footer_note':ParagraphStyle('FN', fontName='Helvetica-Oblique', fontSize=7.5, textColor=_TEXT_GRAY, leading=10),
        'th':         ParagraphStyle('TH', fontName='Helvetica-Bold', fontSize=8, textColor=_WHITE),
        'td':         ParagraphStyle('TD', fontName='Helvetica', fontSize=8, textColor=_TEXT_DARK, leading=11),
    }

    def section_header(title):
        t = Table([[Paragraph(title.upper(), ST['section'])]], colWidths=[CONTENT_W])
        t.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), _DARK_BLUE),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
            ('TOPPADDING',    (0,0),(-1,-1), 7),
            ('BOTTOMPADDING', (0,0),(-1,-1), 7),
            ('LINEBELOW',     (0,0),(-1,-1), 2, _GOLD),
        ]))
        return t

    def info_grid(items, cols=2):
        cell_w = (CONTENT_W - (cols - 1) * 4) / cols
        rows = []
        for i in range(0, len(items), cols):
            row = []
            for label, value in items[i:i+cols]:
                cell = Table(
                    [[Paragraph(label, ST['label'])], [Paragraph(str(value), ST['value'])]],
                    colWidths=[cell_w],
                )
                cell.setStyle(TableStyle([
                    ('BACKGROUND',    (0,0),(-1,-1), _LIGHT_GRAY),
                    ('LEFTPADDING',   (0,0),(-1,-1), 10),
                    ('RIGHTPADDING',  (0,0),(-1,-1), 10),
                    ('TOPPADDING',    (0,0),(-1,-1), 8),
                    ('BOTTOMPADDING', (0,0),(-1,-1), 8),
                    ('LINEBELOW',     (0,0),(-1,-1), 1.5, _GOLD),
                ]))
                row.append(cell)
            while len(row) < cols:
                row.append('')
            rows.append(row)
        t = Table(rows, colWidths=[cell_w] * cols, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
            ('LEFTPADDING',   (0,0),(-1,-1), 2),
            ('RIGHTPADDING',  (0,0),(-1,-1), 2),
            ('TOPPADDING',    (0,0),(-1,-1), 2),
            ('BOTTOMPADDING', (0,0),(-1,-1), 2),
        ]))
        return t

    def data_table(headers, rows_data, col_ratios):
        col_widths = [CONTENT_W * r for r in col_ratios]
        data = [[Paragraph(h, ST['th']) for h in headers]]
        for row in rows_data:
            data.append([Paragraph(str(c), ST['td']) for c in row])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND',     (0,0),(-1,0),  _DARK_BLUE),
            ('LINEBELOW',      (0,0),(-1,0),  2, _GOLD),
            ('ROWBACKGROUNDS', (0,1),(-1,-1), [_WHITE, _LIGHT_GRAY]),
            ('GRID',           (0,0),(-1,-1), 0.3, _MID_GRAY),
            ('LEFTPADDING',    (0,0),(-1,-1), 7),
            ('RIGHTPADDING',   (0,0),(-1,-1), 7),
            ('TOPPADDING',     (0,0),(-1,-1), 5),
            ('BOTTOMPADDING',  (0,0),(-1,-1), 5),
            ('VALIGN',         (0,0),(-1,-1), 'MIDDLE'),
        ]))
        return t

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN_H, rightMargin=MARGIN_H,
        topMargin=48 * mm, bottomMargin=24 * mm,
        title=f'Fiche Utilisateur — {ref_doc}',
        author='Proxim Admin',
        subject='Fiche administrative utilisateur',
    )

    story = []

    title_row = Table(
        [[
            Paragraph('<b>FICHE UTILISATEUR</b>', ST['main_title']),
            Paragraph(f'Identifiant : <b><font color="#F4A922">#{user.id}</font></b>', ST['id_right']),
        ]],
        colWidths=[CONTENT_W * 0.6, CONTENT_W * 0.4],
    )
    title_row.setStyle(TableStyle([
        ('VALIGN',        (0,0),(-1,-1), 'BOTTOM'),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ('TOPPADDING',    (0,0),(-1,-1), 0),
        ('BOTTOMPADDING', (0,0),(-1,-1), 0),
    ]))
    story.append(title_row)
    story.append(Spacer(1, 3))
    deco = Table([['', '']], colWidths=[4, CONTENT_W - 4])
    deco.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(0,0), _GOLD),
        ('BACKGROUND',    (1,0),(1,0), _MID_GRAY),
        ('TOPPADDING',    (0,0),(-1,-1), 0),
        ('BOTTOMPADDING', (0,0),(-1,-1), 0),
        ('LEFTPADDING',   (0,0),(-1,-1), 0),
        ('RIGHTPADDING',  (0,0),(-1,-1), 0),
        ('ROWHEIGHT',     (0,0),(-1,-1), 3),
    ]))
    story.append(deco)
    story.append(Spacer(1, 12))

    story.append(KeepTogether([
        section_header('Informations generales'),
        Spacer(1, 6),
        info_grid([
            ('Email',              user.email),
            ('Role',               user.role.upper()),
            ('Telephone',          user.phone or '—'),
            ("Date d'inscription", user.date_joined.strftime('%d/%m/%Y')),
            ('Email verifie',      'Oui' if user.is_email_verified else 'Non'),
            ('Compte actif',       'Oui' if user.is_active else 'Non'),
        ]),
        Spacer(1, 12),
    ]))

    if profil:
        nom_complet = f"{getattr(profil, 'prenom', '')} {getattr(profil, 'nom', '')}".strip() or '—'
        adresse = getattr(profil, 'adresse', '') or '—'
        profil_items = [('Nom complet', nom_complet), ('Adresse', adresse)]
        if user.role == 'prestataire':
            bio = profil.bio or '—'
            profil_items += [
                ('Niveau',       profil.niveau.upper()),
                ('Note moyenne', f'{profil.note_moyenne}/5  ({profil.nombre_avis} avis)'),
                ('KYC Verifie',  'Oui' if profil.is_verified else 'Non'),
                ('Bio',          (bio[:80] + '...') if len(bio) > 80 else bio),
            ]
        story.append(KeepTogether([
            section_header('Profil'),
            Spacer(1, 6),
            info_grid(profil_items),
            Spacer(1, 12),
        ]))

    if wallet:
        story.append(section_header('Portefeuille'))
        story.append(Spacer(1, 6))
        w_cell_w = (CONTENT_W / 2) - 2
        w_tbl = Table(
            [[
                Table([[Paragraph('Solde actuel', ST['label'])], [Paragraph(f'{wallet.solde} {wallet.devise}', ST['value_green'])]], colWidths=[w_cell_w]),
                Table([[Paragraph('Devise', ST['label'])], [Paragraph(str(wallet.devise), ST['value'])]], colWidths=[w_cell_w]),
            ]],
            colWidths=[w_cell_w + 2] * 2,
        )
        w_tbl.setStyle(TableStyle([
            ('BACKGROUND',    (0,0),(-1,-1), _LIGHT_GRAY),
            ('LINEBELOW',     (0,0),(-1,-1), 1.5, _GOLD),
            ('LEFTPADDING',   (0,0),(-1,-1), 10),
            ('RIGHTPADDING',  (0,0),(-1,-1), 10),
            ('TOPPADDING',    (0,0),(-1,-1), 10),
            ('BOTTOMPADDING', (0,0),(-1,-1), 10),
            ('VALIGN',        (0,0),(-1,-1), 'TOP'),
        ]))
        story.append(w_tbl)
        story.append(Spacer(1, 12))

    if commandes:
        cmd_rows = [
            [f'#{cmd.id}', cmd.service.titre[:38], cmd.statut,
             str(cmd.prix_final or cmd.prix_propose or '—'), cmd.date_commande.strftime('%d/%m/%Y')]
            for cmd in commandes
        ]
        story.append(KeepTogether([
            section_header(f'Historique commandes ({len(commandes)})'),
            Spacer(1, 6),
            data_table(['N°', 'Service', 'Statut', 'Prix final', 'Date'], cmd_rows, [0.08, 0.42, 0.18, 0.16, 0.16]),
            Spacer(1, 12),
        ]))

    if avis:
        note_moy = sum(a.note for a in avis) / len(avis)
        avis_rows = [
            ['★' * a.note + '☆' * (5 - a.note),
             (a.commentaire[:65] + '...') if a.commentaire and len(a.commentaire) > 65 else (a.commentaire or '—'),
             a.date.strftime('%d/%m/%Y')]
            for a in avis
        ]
        story.append(KeepTogether([
            section_header(f'Avis clients ({len(avis)})  —  Moyenne : {note_moy:.1f} / 5'),
            Spacer(1, 6),
            data_table(['Note', 'Commentaire', 'Date'], avis_rows, [0.14, 0.68, 0.18]),
            Spacer(1, 12),
        ]))

    note_tbl = Table(
        [[Paragraph(
            '<i>Ce document est genere automatiquement par le systeme Proxim Admin. '
            'Il est strictement confidentiel et destine uniquement a l\'usage interne '
            'des administrateurs habilites. Toute reproduction ou diffusion non autorisee '
            'est interdite conformement aux conditions generales d\'utilisation.</i>',
            ST['footer_note']
        )]],
        colWidths=[CONTENT_W],
    )
    note_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0,0),(-1,-1), _GOLD_LIGHT),
        ('LEFTPADDING',   (0,0),(-1,-1), 12),
        ('RIGHTPADDING',  (0,0),(-1,-1), 12),
        ('TOPPADDING',    (0,0),(-1,-1), 8),
        ('BOTTOMPADDING', (0,0),(-1,-1), 8),
        ('LINEBEFORE',    (0,0),(0,-1),  3, _GOLD),
    ]))
    story.append(note_tbl)

    cb = lambda c, d: _proxim_page_chrome(c, d, ref_doc, now_str, gen_date)
    doc.build(story, onFirstPage=cb, onLaterPages=cb)

    buffer.seek(0)
    response = HttpResponse(buffer.read(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{ref_doc}_{user.email.split("@")[0]}.pdf"'
    return response


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
    ctx = {'services': svcs, 'categories': categories, 'total': svcs.count(), 'q': q, 'categorie_id': categorie_id, 'statut': statut, 'page': 'services'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/services.html', ctx)


@admin_required
def toggle_service(request, service_id):
    if request.method == 'POST':
        svc = get_object_or_404(Service, id=service_id)
        svc.is_available = not svc.is_available
        svc.save()
        return JsonResponse({'success': True, 'is_available': svc.is_available, 'message': f'Service {"activé" if svc.is_available else "désactivé"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_service(request, service_id):
    if request.method == 'POST':
        get_object_or_404(Service, id=service_id).delete()
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
        # ← commandes terminées avec fonds encore en escrow
        'a_valider': Payment.objects.filter(
            statut='SUCCES', fonds_bloques=True, order__statut='TERMINE'
        ).count(),
    }
    ctx = {'commandes': cmds, 'stats': stats, 'statut': statut, 'q': q, 'page': 'commandes'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/commandes.html', ctx)


@admin_required
def detail_commande(request, commande_id):
    commande = get_object_or_404(
        Order.objects.select_related('client', 'prestatire', 'service'),
        id=commande_id
    )
    historique = commande.historique_statuts.all().order_by('date')
    negotiations = commande.negotiations.all().order_by('date')
    try:
        paiement = commande.payment
    except Exception:
        paiement = None
    try:
        review = commande.review
    except Exception:
        review = None

    ctx = {
        'commande': commande,
        'historique': historique,
        'negotiations': negotiations,
        'paiement': paiement,
        'review': review,
        'page': 'commandes',
    }
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/detail_commande.html', ctx)


# ── Validation fin de service (virement escrow → wallet prestataire) ──────────

@admin_required
def valider_fin_service(request, commande_id):
    """
    L'admin valide la fin de service et declenche le virement
    des fonds bloques vers le wallet du prestataire.
    Conditions : commande TERMINE + paiement SUCCES + fonds encore bloques.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Methode non autorisee'}, status=405)

    from django.db import transaction as db_transaction
    from decimal import Decimal
    from payments.views import crediter_wallet
    from notifications.utils import notif_virement_effectue

    commande = get_object_or_404(Order, id=commande_id)

    if commande.statut != Order.STATUT_TERMINE:
        return JsonResponse(
            {'error': f'La commande doit etre au statut TERMINE (actuel : {commande.statut})'},
            status=400
        )

    try:
        paiement = commande.payment
    except Exception:
        return JsonResponse(
            {'error': 'Aucun paiement trouve pour cette commande'},
            status=400
        )

    if paiement.statut != 'SUCCES':
        return JsonResponse(
            {'error': 'Le paiement n est pas confirme (statut != SUCCES)'},
            status=400
        )

    if not paiement.fonds_bloques:
        return JsonResponse(
            {'error': 'Les fonds ont deja ete vires au prestataire'},
            status=400
        )

    with db_transaction.atomic():
        crediter_wallet(
            commande.prestatire.user,
            paiement.montant_prestatire,
            f'Virement commande #{commande.id} valide par admin'
        )
        paiement.fonds_bloques = False
        paiement.date_virement = timezone.now()
        paiement.save()

        try:
            notif_virement_effectue(paiement)
        except Exception:
            pass

    return JsonResponse({
        'success': True,
        'message': (
            f'Virement de {paiement.montant_prestatire} FCFA effectue vers le wallet '
            f'de {commande.prestatire.prenom} {commande.prestatire.nom}'
        ),
        'montant_vire': str(paiement.montant_prestatire),
        'prestataire': f'{commande.prestatire.prenom} {commande.prestatire.nom}',
    })


# ── Paiements ─────────────────────────────────────────────────

@admin_required
def paiements(request):
    statut = request.GET.get('statut', '')
    methode = request.GET.get('methode', '')
    fonds = request.GET.get('fonds', '')
    pays = Payment.objects.select_related('client', 'order', 'order__service').order_by('-date_paiement')
    if statut:
        pays = pays.filter(statut=statut)
    if methode:
        pays = pays.filter(methode=methode)
    if fonds == 'bloques':
        pays = pays.filter(fonds_bloques=True)
    elif fonds == 'liberes':
        pays = pays.filter(fonds_bloques=False)
    total_succes = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('montant_total'))['t'] or 0
    commission_totale = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('commission_plateforme'))['t'] or 0
    fonds_bloques_total = Payment.objects.filter(statut='SUCCES', fonds_bloques=True).aggregate(t=Sum('montant_prestatire'))['t'] or 0
    ctx = {
        'paiements': pays,
        'total_succes': total_succes,
        'commission_totale': commission_totale,
        'fonds_bloques_total': fonds_bloques_total,
        'statut': statut,
        'methode': methode,
        'fonds': fonds,
        'page': 'paiements',
    }
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/paiements.html', ctx)


# ── Retraits ──────────────────────────────────────────────────

@admin_required
def retraits(request):
    statut = request.GET.get('statut', '')
    rets = Withdrawal.objects.select_related('prestatire', 'prestatire__user').order_by('-date_demande')
    if statut:
        rets = rets.filter(statut=statut)
    total_en_attente = Withdrawal.objects.filter(statut='EN_ATTENTE').aggregate(t=Sum('montant'))['t'] or 0
    ctx = {'retraits': rets, 'total_en_attente': total_en_attente, 'statut': statut, 'page': 'retraits'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/retraits.html', ctx)


@admin_required
def traiter_retrait(request, retrait_id):
    if request.method == 'POST':
        retrait = get_object_or_404(Withdrawal, id=retrait_id)
        action = request.POST.get('action')
        retrait.statut = 'TRAITE' if action == 'traiter' else 'REJETE'
        retrait.date_traitement = timezone.now()
        retrait.save()
        msg = 'Retrait marqué comme traité' if action == 'traiter' else 'Retrait rejeté'
        try:
            Notification.objects.create(
                destinataire=retrait.prestatire.user, type='RETRAIT_TRAITE',
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
    ctx = {'documents': docs, 'stats': stats, 'statut': statut, 'page': 'kyc'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/kyc.html', ctx)


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
    ctx = {'categories': cats, 'total': cats.count(), 'page': 'categories'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/categories.html', ctx)


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
    ctx = {'signalements': sigs, 'stats': stats, 'statut': statut, 'raison': raison, 'page': 'signalements'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/signalements.html', ctx)


@admin_required
def traiter_signalement(request, sig_id):
    if request.method == 'POST':
        sig = get_object_or_404(Report, id=sig_id)
        action = request.POST.get('action')
        if action == 'traiter':
            sig.statut = 'TRAITE'
            sig.save()
            return JsonResponse({'success': True, 'message': 'Signalement traité'})
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
        all_avis = all_avis.filter(Q(client__nom__icontains=q) | Q(prestatire__nom__icontains=q) | Q(commentaire__icontains=q))
    stats = {
        'total': Review.objects.count(),
        'note_moy': Review.objects.aggregate(m=Avg('note'))['m'] or 0,
        'cinq': Review.objects.filter(note=5).count(),
        'un': Review.objects.filter(note=1).count(),
    }
    ctx = {'avis': all_avis, 'stats': stats, 'note_min': note_min, 'q': q, 'page': 'avis'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/avis.html', ctx)


@admin_required
def supprimer_avis(request, avis_id):
    if request.method == 'POST':
        get_object_or_404(Review, id=avis_id).delete()
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
    ctx = {'posts': all_posts, 'total': all_posts.count(), 'statut': statut, 'q': q, 'page': 'posts'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/posts.html', ctx)


@admin_required
def toggle_post(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        post.is_active = not post.is_active
        post.save()
        return JsonResponse({'success': True, 'is_active': post.is_active, 'message': f'Post {"activé" if post.is_active else "masqué"}'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def supprimer_post(request, post_id):
    if request.method == 'POST':
        get_object_or_404(Post, id=post_id).delete()
        return JsonResponse({'success': True, 'message': 'Post supprimé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


# ── Messagerie ────────────────────────────────────────────────

@admin_required
def messagerie(request):
    q = request.GET.get('q', '')
    convs = Conversation.objects.select_related('client', 'prestatire').annotate(
        nb_messages=Count('messages'),
        nb_suspects=Count('messages', filter=Q(messages__is_deleted=False))
    ).order_by('-dernier_message_date')
    if q:
        convs = convs.filter(
            Q(client__nom__icontains=q) | Q(client__prenom__icontains=q) |
            Q(prestatire__nom__icontains=q) | Q(prestatire__prenom__icontains=q)
        )
    total_messages = Message.objects.count()
    total_non_lus = Message.objects.filter(is_read=False).count()
    messages_suspects = Message.objects.filter(is_deleted=True).select_related(
        'conversation__client', 'conversation__prestatire', 'expediteur'
    ).order_by('-date_envoi')[:20]
    ctx = {
        'conversations': convs, 'total_messages': total_messages,
        'total_non_lus': total_non_lus, 'messages_suspects': messages_suspects,
        'q': q, 'page': 'messagerie'
    }
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/messagerie.html', ctx)


@admin_required
def detail_conversation(request, conv_id):
    conv = get_object_or_404(Conversation.objects.select_related('client', 'prestatire'), id=conv_id)
    messages_list = conv.messages.select_related('expediteur').order_by('date_envoi')
    ctx = {'conv': conv, 'messages_list': messages_list, 'page': 'messagerie'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/detail_conversation.html', ctx)


@admin_required
def signaler_message(request, conv_id):
    if request.method == 'POST':
        message_id = request.POST.get('message_id')
        msg = get_object_or_404(Message, id=message_id, conversation_id=conv_id)
        msg.is_deleted = True
        msg.save()
        try:
            Report.objects.create(
                reporter=request.user,
                cible_user=msg.expediteur,
                raison='CONTENU_INAPPROPRIE',
                description=f'Message suspect signalé par l\'admin (ID message: {msg.id}). Contenu: {msg.contenu[:100]}',
                statut='EN_ATTENTE',
            )
        except Exception:
            pass
        return JsonResponse({'success': True, 'message': 'Message signalé et signalement créé'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)


@admin_required
def ecrire_utilisateurs(request):
    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        contenu = request.POST.get('contenu', '').strip()
        cible = request.POST.get('cible', 'tous')
        user_id = request.POST.get('user_id', '')
        if not titre or not contenu:
            return JsonResponse({'error': 'Titre et contenu obligatoires'}, status=400)
        if user_id:
            user = get_object_or_404(User, id=user_id)
            Notification.objects.create(destinataire=user, type='NOUVEAU_MESSAGE', titre=titre, contenu=contenu)
            return JsonResponse({'success': True, 'message': f'Message envoyé à {user.email}'})
        users = User.objects.filter(is_active=True)
        if cible == 'clients':
            users = users.filter(role='client')
        elif cible == 'prestataires':
            users = users.filter(role='prestataire')
        notifs = [Notification(destinataire=u, type='NOUVEAU_MESSAGE', titre=titre, contenu=contenu) for u in users]
        Notification.objects.bulk_create(notifs)
        return JsonResponse({'success': True, 'message': f'{len(notifs)} message(s) envoyé(s)'})
    all_users = User.objects.filter(is_active=True).order_by('role', 'email')
    ctx = {'all_users': all_users, 'page': 'messagerie'}
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/ecrire_utilisateurs.html', ctx)


# ── Wallet Plateforme ─────────────────────────────────────────

@admin_required
def wallet_plateforme(request):
    revenus_total = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('commission_plateforme'))['t'] or 0
    retraits_total = Withdrawal.objects.filter(statut='TRAITE').aggregate(t=Sum('montant'))['t'] or 0
    retraits_en_attente_montant = Withdrawal.objects.filter(statut='EN_ATTENTE').aggregate(t=Sum('montant'))['t'] or 0
    volume_total = Payment.objects.filter(statut='SUCCES').aggregate(t=Sum('montant_total'))['t'] or 0
    solde_plateforme = float(volume_total) - float(retraits_total)
    # ← fonds encore en escrow (pas encore virés aux prestataires)
    fonds_en_escrow = Payment.objects.filter(statut='SUCCES', fonds_bloques=True).aggregate(t=Sum('montant_prestatire'))['t'] or 0

    wallets = Wallet.objects.select_related('user').order_by('-solde')
    solde_total_prestataires = wallets.aggregate(t=Sum('solde'))['t'] or 0
    transactions_recentes = Transaction.objects.select_related('wallet__user').order_by('-date')[:20]
    paiements_recents = Payment.objects.filter(statut='SUCCES').select_related('client', 'order__service').order_by('-date_paiement')[:15]

    today = date.today()
    stats_mois = []
    for i in range(5, -1, -1):
        mois = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
        if mois.month < 12:
            fin = mois.replace(month=mois.month + 1, day=1)
        else:
            fin = mois.replace(year=mois.year + 1, month=1, day=1)
        revenus_m = Payment.objects.filter(
            statut='SUCCES', date_paiement__date__gte=mois, date_paiement__date__lt=fin
        ).aggregate(t=Sum('commission_plateforme'))['t'] or 0
        retraits_m = Withdrawal.objects.filter(
            statut='TRAITE', date_traitement__date__gte=mois, date_traitement__date__lt=fin
        ).aggregate(t=Sum('montant'))['t'] or 0
        stats_mois.append({
            'mois': mois.strftime('%b %Y'),
            'revenus': float(revenus_m),
            'retraits': float(retraits_m),
        })

    ctx = {
        'revenus_total': revenus_total,
        'retraits_total': retraits_total,
        'retraits_en_attente_montant': retraits_en_attente_montant,
        'volume_total': volume_total,
        'solde_plateforme': solde_plateforme,
        'fonds_en_escrow': fonds_en_escrow,
        'wallets': wallets,
        'solde_total_prestataires': solde_total_prestataires,
        'transactions_recentes': transactions_recentes,
        'paiements_recents': paiements_recents,
        'stats_mois': stats_mois,
        'page': 'wallet',
    }
    ctx.update(_global_ctx())
    return render(request, 'admin_dashboard/wallet.html', ctx)


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
        Notification.objects.bulk_create([
            Notification(destinataire=u, type='NOUVEAU_MESSAGE', titre=titre, contenu=contenu)
            for u in users
        ])
        return JsonResponse({'success': True, 'message': f'Notification envoyée à {users.count()} utilisateur(s)'})
    return JsonResponse({'error': 'Méthode non autorisée'}, status=405)