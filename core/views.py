from decimal import Decimal
from collections import defaultdict
import json
from .models import CarBlockPeriod
from .forms import AdminCarBlockForm
import base64
import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.decorators import user_passes_test
from .models import SiteSetting, Reservation
from .forms import BookingControlForm, AdminManualReservationForm
from .models import (
    CarModel, CarUnit, Reservation, Payment, Client, FinanceEntry,
    MaintenanceRecord, AccidentRecord, SparePartRecord
)
from .forms import (
    SignUpForm, LoginForm, SearchAvailabilityForm,
    ReservationNormalForm, ReservationCompleteForm,
    CarModelForm, CarUnitForm, CarImageForm, ClientForm,
    ReservationAdminForm, QuickFinanceForm,
    MaintenanceForm, AccidentForm, SparePartForm
)


def staff_required(view_func):
    return login_required(user_passes_test(lambda u: u.is_staff or u.is_superuser)(view_func))

def get_available_units(car_model, date_debut, date_fin, requested_transmission=''):
    units = car_model.units.filter(disponible=True)

    if requested_transmission:
        units = units.filter(transmission=requested_transmission)

    available_units = []

    for unit in units:
        reservation_conflict = Reservation.objects.filter(
            car_unit=unit,
            statut__in=ACTIVE_RESERVATION_STATUSES,
            date_debut__lte=date_fin,
            date_fin__gte=date_debut
        ).exists()

        block_conflict = CarBlockPeriod.objects.filter(
            actif=True,
            date_debut__lte=date_fin,
            date_fin__gte=date_debut
        ).filter(
            models.Q(car_unit=unit) | models.Q(car_model=car_model, car_unit__isnull=True)
        ).exists()

        if not reservation_conflict and not block_conflict:
            available_units.append(unit)

    return available_units
def check_reservation_conflict(car_model, date_debut, date_fin, requested_transmission=''):
    return len(get_available_units(car_model, date_debut, date_fin, requested_transmission)) == 0

def home(request):
    car_models_qs = CarModel.objects.filter(actif=True)
    form = SearchAvailabilityForm(request.GET or None)
    date_debut = None
    date_fin = None
    transmission = ''
    voitures = []

    if form.is_valid():
        date_debut = form.cleaned_data.get('date_debut')
        date_fin = form.cleaned_data.get('date_fin')
        transmission = form.cleaned_data.get('transmission') or ''

    for cm in car_models_qs:
        transmissions = cm.available_transmissions()

        if date_debut and date_fin:
            available_count = cm.available_units_count(date_debut, date_fin, transmission)
            if available_count <= 0:
                continue
        else:
            if transmission:
                available_count = cm.units.filter(active=True, transmission=transmission).count()
                if available_count <= 0:
                    continue
            else:
                available_count = cm.units.filter(active=True).count()

        cm.available_count = available_count
        cm.transmissions_display = ", ".join(
            ["Manuelle" if t == "manuelle" else "Automatique" if t == "automatique" else t for t in transmissions]
        )
        voitures.append(cm)

    return render(request, 'home.html', {
        'voitures': voitures,
        'search_form': form,
        'selected_date_debut': date_debut,
        'selected_date_fin': date_fin,
        'selected_transmission': transmission,
    })

def car_detail(request, car_id):
    voiture = get_object_or_404(CarModel, id=car_id, actif=True)
    galerie = voiture.images.all()
    transmissions = voiture.available_transmissions()
    return render(request, 'car_detail.html', {
        'voiture': voiture,
        'galerie': galerie,
        'transmissions': transmissions,
    })
def choose_reservation_type(request, car_id):
    voiture = get_object_or_404(CarModel, id=car_id, actif=True)
    transmissions = voiture.available_transmissions()

    selected_transmission = request.GET.get('transmission', '').strip()

    if len(transmissions) == 1:
        selected_transmission = transmissions[0]

    if selected_transmission and selected_transmission not in transmissions:
        selected_transmission = ''

    site_settings = SiteSetting.load()

    return render(request, 'choose_reservation_type.html', {
        'voiture': voiture,
        'transmissions': transmissions,
        'selected_transmission': selected_transmission,
        'allow_normal_booking': site_settings.allow_normal_booking,
        'allow_online_payment': site_settings.allow_online_payment,
    })

def signup_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Compte créé avec succès.")
            return redirect('home')
        messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('dashboard')
        return redirect('home')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = authenticate(
            request,
            username=form.cleaned_data['username'],
            password=form.cleaned_data['password']
        )
        if user:
            login(request, user)
            if user.is_staff or user.is_superuser:
                return redirect('dashboard')
            return redirect('home')
        messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home')
def reservation_normal(request, car_id):
    voiture = get_object_or_404(CarModel, id=car_id, actif=True)

    site_settings = SiteSetting.load()
    if not site_settings.allow_normal_booking:
        messages.error(request, "La réservation normale est actuellement indisponible.")
        return redirect('choose_reservation_type', car_id=car_id)

    transmissions = voiture.available_transmissions()

    preselected_transmission = request.GET.get('transmission', '').strip()
    if len(transmissions) == 1:
        preselected_transmission = transmissions[0]

    form = ReservationNormalForm(request.POST or None)

    if request.method == 'GET' and preselected_transmission:
        form.fields['requested_transmission'].initial = preselected_transmission

    if request.method == 'POST' and form.is_valid():
        date_debut = form.cleaned_data['date_debut']
        date_fin = form.cleaned_data['date_fin']
        requested_transmission = form.cleaned_data.get('requested_transmission') or ''

        if len(transmissions) == 1 and not requested_transmission:
            requested_transmission = transmissions[0]

        if date_fin < date_debut:
            messages.error(request, "La date de fin doit être après la date de début.")
        elif check_reservation_conflict(voiture, date_debut, date_fin, requested_transmission):
            messages.error(request, "Aucune unité disponible pour cette période avec ce choix de transmission.")
        else:
            unit = get_available_units(voiture, date_debut, date_fin, requested_transmission)[0]

            reservation = form.save(commit=False)
            reservation.car_model = voiture
            reservation.car_unit = unit
            reservation.requested_transmission = requested_transmission
            reservation.type_reservation = 'normale'
            reservation.statut = 'en_attente'
            reservation.kilometrage_depart = unit.kilometrage_actuel

            if request.user.is_authenticated:
                reservation.user = request.user
                client = getattr(request.user, 'client_profile', None)
                if client:
                    reservation.client = client

            reservation.save()

            messages.success(request, "Votre demande de réservation a été envoyée avec succès.")
            if request.user.is_authenticated:
                return redirect('my_reservations')
            return redirect('home')

    return render(request, 'reservation_normal.html', {
        'form': form,
        'voiture': voiture,
        'selected_transmission': preselected_transmission,
        'transmissions': transmissions,
    })
def reservation_complete(request, car_id):
    voiture = get_object_or_404(CarModel, id=car_id, actif=True)

    site_settings = SiteSetting.load()
    if not site_settings.allow_online_payment:
        messages.error(request, "Le paiement en ligne est actuellement indisponible.")
        return redirect('choose_reservation_type', car_id=car_id)

    transmissions = voiture.available_transmissions()

    preselected_transmission = request.GET.get('transmission', '').strip()
    if len(transmissions) == 1:
        preselected_transmission = transmissions[0]

    form = ReservationCompleteForm(request.POST or None)

    if request.method == 'GET' and preselected_transmission:
        form.fields['requested_transmission'].initial = preselected_transmission

    if request.method == 'POST' and form.is_valid():
        date_debut = form.cleaned_data['date_debut']
        date_fin = form.cleaned_data['date_fin']
        requested_transmission = form.cleaned_data.get('requested_transmission') or ''

        if len(transmissions) == 1 and not requested_transmission:
            requested_transmission = transmissions[0]

        if date_fin < date_debut:
            messages.error(request, "La date de fin doit être après la date de début.")
        elif check_reservation_conflict(voiture, date_debut, date_fin, requested_transmission):
            messages.error(request, "Aucune unité disponible pour cette période avec ce choix de transmission.")
        else:
            client = getattr(request.user, 'client_profile', None)
            unit = get_available_units(voiture, date_debut, date_fin, requested_transmission)[0]

            reservation = form.save(commit=False)
            reservation.car_model = voiture
            reservation.car_unit = unit
            reservation.user = request.user
            reservation.client = client
            reservation.requested_transmission = requested_transmission
            reservation.type_reservation = 'complete'
            reservation.nom_complet = f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username
            reservation.email = request.user.email
            reservation.telephone = client.telephone if client else ''
            reservation.adresse = client.adresse if client else ''
            reservation.cin = client.cin if client else ''
            reservation.numero_permis = client.numero_permis if client else ''
            reservation.statut = 'paiement_en_attente'
            reservation.kilometrage_depart = unit.kilometrage_actuel
            reservation.save()

            return redirect('checkout', reservation_id=reservation.id)

    return render(request, 'reservation_complete.html', {
        'form': form,
        'voiture': voiture,
        'selected_transmission': preselected_transmission,
        'transmissions': transmissions,
    })
@login_required
def my_reservations(request):
    reservations = Reservation.objects.filter(
        user=request.user
    ).select_related('car_model', 'car_unit').order_by('-created_at')

    # secours si anciennes réservations liées seulement par email
    if not reservations.exists() and request.user.email:
        reservations = Reservation.objects.filter(
            email=request.user.email
        ).select_related('car_model', 'car_unit').order_by('-created_at')

    return render(request, 'my_reservations.html', {'reservations': reservations})


@login_required
def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    if reservation.peut_etre_annulee_par_client():
        reservation.statut = 'annulee'
        reservation.est_annulable = False
        reservation.save()
        messages.success(request, "Réservation annulée.")
    else:
        messages.error(request, "Cette réservation ne peut plus être annulée.")

    return redirect('my_reservations')


@login_required
def checkout(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)
    return render(request, 'checkout.html', {
        'reservation': reservation,
        'PAYPAL_CLIENT_ID': settings.PAYPAL_CLIENT_ID,
    })
@login_required
@csrf_exempt
def paypal_create_order(request, reservation_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    try:
        access_token = get_paypal_access_token()

        # Conversion DH -> EUR
        taux = 0.092
        montant_eur = float(reservation.montant_total) * taux

        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": str(reservation.id),
                    "amount": {
                        "currency_code": "EUR",
                        "value": format(montant_eur, '.2f')
                    },
                    "description": f"Réservation #{reservation.id} - {reservation.car_model}"
                }
            ]
        }

        response = requests.post(
            f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            data=json.dumps(payload),
            timeout=30,
        )

        if response.status_code not in [200, 201]:
            return JsonResponse({
                "error": "Impossible de créer la commande PayPal",
                "details": response.text
            }, status=400)

        data = response.json()
        return JsonResponse({"id": data["id"]})

    except Exception as e:
        return JsonResponse({
            "error": "Erreur création commande PayPal",
            "details": str(e)
        }, status=500)
@login_required
@csrf_exempt
def paypal_capture_order(request, reservation_id):
    if request.method != "POST":
        return JsonResponse({"error": "Méthode non autorisée"}, status=405)

    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "JSON invalide"}, status=400)

    order_id = body.get("orderID")
    if not order_id:
        return JsonResponse({"error": "orderID manquant"}, status=400)

    access_token = get_paypal_access_token()

    response = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        timeout=30,
    )

    if response.status_code not in [200, 201]:
        return JsonResponse({
            "error": "Capture PayPal échouée",
            "details": response.text
        }, status=400)

    capture_data = response.json()

    payment, created = Payment.objects.get_or_create(
        reservation=reservation,
        defaults={
            "montant": reservation.montant_total,
            "provider": "paypal",
            "transaction_id": order_id,
            "status": "success",
        }
    )

    if not created:
        payment.provider = "paypal"
        payment.transaction_id = order_id
        payment.status = "success"
        payment.montant = reservation.montant_total
        payment.save()

    reservation.statut = "payee"
    reservation.est_annulable = False
    reservation.save()

    FinanceEntry.objects.create(
        titre=f"Paiement PayPal réservation #{reservation.id}",
        operation_type="location",
        montant=reservation.montant_total,
        date=reservation.date_debut,
        tiers_nom=reservation.nom_complet,
        car_model=reservation.car_model,
        car_unit=reservation.car_unit,
        client=reservation.client,
        reservation=reservation,
        note="Paiement PayPal capturé automatiquement"
    )

    return JsonResponse({
        "status": "success",
        "details": capture_data
    })

@login_required
def payment_success_demo(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    payment, created = Payment.objects.get_or_create(
        reservation=reservation,
        defaults={
            'montant': reservation.montant_total,
            'provider': 'demo',
            'transaction_id': f'DEMO-{reservation.id}',
            'status': 'success'
        }
    )

    if not created:
        payment.status = 'success'
        payment.transaction_id = f'DEMO-{reservation.id}'
        payment.montant = reservation.montant_total
        payment.save()

    reservation.statut = 'payee'
    reservation.est_annulable = False
    reservation.save()

    FinanceEntry.objects.create(
        titre=f"Paiement réservation #{reservation.id}",
        operation_type='location',
        montant=reservation.montant_total,
        date=reservation.date_debut,
        tiers_nom=reservation.nom_complet,
        car_model=reservation.car_model,
        car_unit=reservation.car_unit,
        client=reservation.client,
        reservation=reservation,
        note='Paiement enregistré automatiquement'
    )

    messages.success(request, "Paiement simulé avec succès.")
    return redirect('my_reservations')


@staff_required
def dashboard(request):
    entries = FinanceEntry.objects.all().order_by('date')
    car_models = CarModel.objects.all()

    total_income = sum(e.montant for e in entries if e.is_positive)
    total_expense = sum(e.montant for e in entries if not e.is_positive)
    net_profit = total_income - total_expense

    total_clients = Client.objects.count()
    total_models = CarModel.objects.count()
    total_units = CarUnit.objects.count()
    total_reservations = Reservation.objects.count()
    pending_reservations = Reservation.objects.filter(statut='en_attente').count()

    monthly_data = defaultdict(lambda: {'income': Decimal('0.00'), 'expense': Decimal('0.00')})
    for entry in entries:
        month_label = entry.date.strftime('%Y-%m')
        if entry.is_positive:
            monthly_data[month_label]['income'] += entry.montant
        else:
            monthly_data[month_label]['expense'] += entry.montant

    months = sorted(monthly_data.keys())
    monthly_income = [float(monthly_data[m]['income']) for m in months]
    monthly_expense = [float(monthly_data[m]['expense']) for m in months]

    car_labels = []
    car_income_data = []
    car_expense_data = []
    car_net_data = []
    car_stats = []

    for cm in car_models:
        cm_entries = cm.finance_entries.all()
        income = sum(e.montant for e in cm_entries if e.is_positive)
        expense = sum(e.montant for e in cm_entries if not e.is_positive)
        net = income - expense

        car_labels.append(f"{cm.marque} {cm.modele}")
        car_income_data.append(float(income))
        car_expense_data.append(float(expense))
        car_net_data.append(float(net))

        car_stats.append({
            'car_model': cm,
            'income': income,
            'expense': expense,
            'net': net,
            'reservations': cm.reservations.count(),
            'units': cm.units.count(),
        })

    operation_totals = defaultdict(float)
    for entry in entries:
        operation_totals[entry.get_operation_type_display()] += float(entry.montant)

    context = {
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'total_clients': total_clients,
        'total_models': total_models,
        'total_units': total_units,
        'total_reservations': total_reservations,
        'pending_reservations': pending_reservations,
        'car_stats': car_stats,

        'months_json': json.dumps(months),
        'monthly_income_json': json.dumps(monthly_income),
        'monthly_expense_json': json.dumps(monthly_expense),

        'car_labels_json': json.dumps(car_labels),
        'car_income_json': json.dumps(car_income_data),
        'car_expense_json': json.dumps(car_expense_data),
        'car_net_json': json.dumps(car_net_data),

        'pie_labels_json': json.dumps(list(operation_totals.keys())),
        'pie_values_json': json.dumps(list(operation_totals.values())),
    }
    return render(request, 'dashboard/dashboard.html', context)


@staff_required
def dashboard_car_models(request):
    cars = CarModel.objects.all()
    return render(request, 'dashboard/car_models_list.html', {'cars': cars})


@staff_required
def dashboard_car_model_add(request):
    form = CarModelForm(request.POST or None, request.FILES or None)
    image_form = CarImageForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        car = form.save()
        if request.FILES.get('image') and image_form.is_valid():
            gallery = image_form.save(commit=False)
            gallery.car_model = car
            gallery.save()
        messages.success(request, "Fiche modèle ajoutée.")
        return redirect('dashboard_car_models')

    return render(request, 'dashboard/car_model_form.html', {
        'form': form,
        'image_form': image_form,
        'title': 'Ajouter fiche modèle'
    })


@staff_required
def dashboard_car_model_edit(request, car_id):
    car = get_object_or_404(CarModel, id=car_id)
    form = CarModelForm(request.POST or None, request.FILES or None, instance=car)
    image_form = CarImageForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        form.save()
        if request.FILES.get('image') and image_form.is_valid():
            gallery = image_form.save(commit=False)
            gallery.car_model = car
            gallery.save()
        messages.success(request, "Fiche modèle modifiée.")
        return redirect('dashboard_car_models')

    return render(request, 'dashboard/car_model_form.html', {
        'form': form,
        'image_form': image_form,
        'car': car,
        'title': 'Modifier fiche modèle'
    })


@staff_required
def dashboard_car_model_delete(request, car_id):
    car = get_object_or_404(CarModel, id=car_id)
    car.delete()
    messages.success(request, "Fiche modèle supprimée.")
    return redirect('dashboard_car_models')


@staff_required
def dashboard_car_units(request):
    units = CarUnit.objects.select_related('car_model').all()
    return render(request, 'dashboard/car_units_list.html', {'units': units})


@staff_required
def dashboard_car_unit_add(request):
    form = CarUnitForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Unité ajoutée.")
        return redirect('dashboard_car_units')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter unité réelle'})


@staff_required
def dashboard_car_unit_edit(request, unit_id):
    unit = get_object_or_404(CarUnit, id=unit_id)
    form = CarUnitForm(request.POST or None, instance=unit)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Unité modifiée.")
        return redirect('dashboard_car_units')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier unité réelle'})


@staff_required
def dashboard_car_unit_delete(request, unit_id):
    unit = get_object_or_404(CarUnit, id=unit_id)
    unit.delete()
    messages.success(request, "Unité supprimée.")
    return redirect('dashboard_car_units')


@staff_required
def dashboard_clients(request):
    clients = Client.objects.all()
    return render(request, 'dashboard/clients_list.html', {'clients': clients})


@staff_required
def dashboard_client_add(request):
    form = ClientForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Client ajouté.")
        return redirect('dashboard_clients')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter client'})


@staff_required
def dashboard_client_edit(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    form = ClientForm(request.POST or None, instance=client)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Client modifié.")
        return redirect('dashboard_clients')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier client'})


@staff_required
def dashboard_client_delete(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.delete()
    messages.success(request, "Client supprimé.")
    return redirect('dashboard_clients')


@staff_required
def dashboard_reservations(request):
    reservations = Reservation.objects.select_related('car_model', 'car_unit', 'client').all()
    return render(request, 'dashboard/reservations_list.html', {'reservations': reservations})


@staff_required
def dashboard_reservation_add(request):
    form = ReservationAdminForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        reservation = form.save(commit=False)
        requested_transmission = form.cleaned_data.get('requested_transmission') or ''

        if reservation.car_unit:
            if reservation.car_unit.car_model_id != reservation.car_model_id:
                messages.error(request, "L’unité choisie n’appartient pas à ce modèle.")
            elif not reservation.car_unit.is_available_for_period(
                form.cleaned_data['date_debut'],
                form.cleaned_data['date_fin']
            ):
                messages.error(request, "Cette unité n’est pas disponible sur cette période.")
            else:
                reservation.kilometrage_depart = reservation.car_unit.kilometrage_actuel
                reservation.save()
                messages.success(request, "Réservation ajoutée.")
                return redirect('dashboard_reservations')
        else:
            units = get_available_units(
                reservation.car_model,
                form.cleaned_data['date_debut'],
                form.cleaned_data['date_fin'],
                requested_transmission=requested_transmission
            )
            if not units:
                messages.error(request, "Aucune unité disponible pour cette période.")
            else:
                reservation.car_unit = units[0]
                reservation.kilometrage_depart = reservation.car_unit.kilometrage_actuel
                reservation.save()
                messages.success(request, "Réservation ajoutée.")
                return redirect('dashboard_reservations')

    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter réservation'})


@staff_required
def dashboard_reservation_edit(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    form = ReservationAdminForm(request.POST or None, instance=reservation)

    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        requested_transmission = form.cleaned_data.get('requested_transmission') or ''

        if updated.car_unit:
            if updated.car_unit.car_model_id != updated.car_model_id:
                messages.error(request, "L’unité choisie n’appartient pas à ce modèle.")
            elif not updated.car_unit.is_available_for_period(
                form.cleaned_data['date_debut'],
                form.cleaned_data['date_fin'],
                exclude_reservation_id=reservation.id
            ):
                messages.error(request, "Cette unité n’est pas disponible sur cette période.")
            else:
                updated.save()
                if updated.kilometrage_retour and updated.kilometrage_retour > updated.car_unit.kilometrage_actuel:
                    updated.car_unit.kilometrage_actuel = updated.kilometrage_retour
                    updated.car_unit.save()
                messages.success(request, "Réservation modifiée.")
                return redirect('dashboard_reservations')
        else:
            units = get_available_units(
                updated.car_model,
                form.cleaned_data['date_debut'],
                form.cleaned_data['date_fin'],
                requested_transmission=requested_transmission,
                exclude_reservation_id=reservation.id
            )
            if not units:
                messages.error(request, "Aucune unité disponible pour cette période.")
            else:
                updated.car_unit = units[0]
                updated.save()
                if updated.kilometrage_retour and updated.kilometrage_retour > updated.car_unit.kilometrage_actuel:
                    updated.car_unit.kilometrage_actuel = updated.kilometrage_retour
                    updated.car_unit.save()
                messages.success(request, "Réservation modifiée.")
                return redirect('dashboard_reservations')

    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier réservation'})


@staff_required
def dashboard_reservation_delete(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    reservation.delete()
    messages.success(request, "Réservation supprimée.")
    return redirect('dashboard_reservations')


@staff_required
def dashboard_finance(request):
    entries = FinanceEntry.objects.order_by('-date', '-id')[:20]

    all_entries = FinanceEntry.objects.all().order_by('date')
    total_income = sum(e.montant for e in all_entries if e.is_positive)
    total_expense = sum(e.montant for e in all_entries if not e.is_positive)
    net_profit = total_income - total_expense

    monthly_data = defaultdict(lambda: {'income': 0, 'expense': 0})
    for entry in all_entries:
        month_label = entry.date.strftime('%Y-%m')
        if entry.is_positive:
            monthly_data[month_label]['income'] += float(entry.montant)
        else:
            monthly_data[month_label]['expense'] += float(entry.montant)

    months = sorted(monthly_data.keys())
    monthly_income = [monthly_data[m]['income'] for m in months]
    monthly_expense = [monthly_data[m]['expense'] for m in months]

    operation_totals = defaultdict(float)
    for entry in all_entries:
        operation_totals[entry.get_operation_type_display()] += float(entry.montant)

    context = {
        'entries': entries,
        'total_income': total_income,
        'total_expense': total_expense,
        'net_profit': net_profit,
        'months_json': json.dumps(months),
        'monthly_income_json': json.dumps(monthly_income),
        'monthly_expense_json': json.dumps(monthly_expense),
        'pie_labels_json': json.dumps(list(operation_totals.keys())),
        'pie_values_json': json.dumps(list(operation_totals.values())),
    }
    return render(request, 'dashboard/finance_quick.html', context)

@staff_required
def finance_quick_add(request, operation_type):
    allowed_types = [
        'charge_simple', 'revenu_simple', 'salaire', 'loyer',
        'credit_recu', 'remboursement_credit',
        'avance_recue', 'avance_versee',
        'entretien', 'carburant', 'piece', 'accident',
        'location', 'autre'
    ]

    if operation_type not in allowed_types:
        messages.error(request, "Type d’opération invalide.")
        return redirect('dashboard_finance')

    form = QuickFinanceForm(request.POST or None, operation_type=operation_type)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Écriture enregistrée avec succès.")
        return redirect('dashboard_finance')

    operation_labels = {
        'charge_simple': 'Ajouter charge simple',
        'revenu_simple': 'Ajouter revenu simple',
        'salaire': 'Ajouter salaire',
        'loyer': 'Ajouter loyer',
        'credit_recu': 'Ajouter crédit reçu',
        'remboursement_credit': 'Ajouter remboursement crédit',
        'avance_recue': 'Ajouter avance reçue',
        'avance_versee': 'Ajouter avance versée',
        'entretien': 'Ajouter entretien',
        'carburant': 'Ajouter carburant',
        'piece': 'Ajouter pièce',
        'accident': 'Ajouter accident',
        'location': 'Ajouter revenu location',
        'autre': 'Ajouter autre opération',
    }

    return render(request, 'dashboard/finance_quick_form.html', {
        'form': form,
        'title': operation_labels.get(operation_type, 'Ajouter opération'),
        'operation_type': operation_type,
    })

@staff_required
def dashboard_maintenances(request):
    maintenances = MaintenanceRecord.objects.select_related('car_unit', 'car_unit__car_model').all()
    return render(request, 'dashboard/maintenances_list.html', {'maintenances': maintenances})


@staff_required
def dashboard_maintenance_add(request):
    form = MaintenanceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        maintenance = form.save()

        if maintenance.cout > 0:
            FinanceEntry.objects.create(
                titre=f"Entretien - {maintenance.titre}",
                operation_type='entretien',
                montant=maintenance.cout,
                date=maintenance.date_entretien,
                car_model=maintenance.car_unit.car_model,
                car_unit=maintenance.car_unit,
                note=maintenance.description
            )

        maintenance.car_unit.date_prochain_entretien = maintenance.prochain_entretien_date
        if maintenance.kilometrage > maintenance.car_unit.kilometrage_actuel:
            maintenance.car_unit.kilometrage_actuel = maintenance.kilometrage
        maintenance.car_unit.save()

        messages.success(request, "Entretien ajouté.")
        return redirect('dashboard_maintenances')

    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter entretien'})


@staff_required
def dashboard_maintenance_edit(request, maintenance_id):
    maintenance = get_object_or_404(MaintenanceRecord, id=maintenance_id)
    form = MaintenanceForm(request.POST or None, instance=maintenance)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Entretien modifié.")
        return redirect('dashboard_maintenances')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier entretien'})


@staff_required
def dashboard_maintenance_delete(request, maintenance_id):
    maintenance = get_object_or_404(MaintenanceRecord, id=maintenance_id)
    maintenance.delete()
    messages.success(request, "Entretien supprimé.")
    return redirect('dashboard_maintenances')


@staff_required
def dashboard_accidents(request):
    accidents = AccidentRecord.objects.select_related('car_unit', 'car_unit__car_model', 'reservation').all()
    return render(request, 'dashboard/accidents_list.html', {'accidents': accidents})


@staff_required
def dashboard_accident_add(request):
    form = AccidentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        accident = form.save()

        if accident.montant_restant > 0:
            FinanceEntry.objects.create(
                titre=f"Accident - {accident.titre}",
                operation_type='accident',
                montant=accident.montant_restant,
                date=accident.date_accident,
                car_model=accident.car_unit.car_model,
                car_unit=accident.car_unit,
                reservation=accident.reservation,
                note=accident.description
            )

        messages.success(request, "Accident ajouté.")
        return redirect('dashboard_accidents')

    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter accident'})


@staff_required
def dashboard_accident_edit(request, accident_id):
    accident = get_object_or_404(AccidentRecord, id=accident_id)
    form = AccidentForm(request.POST or None, instance=accident)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Accident modifié.")
        return redirect('dashboard_accidents')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier accident'})


@staff_required
def dashboard_accident_delete(request, accident_id):
    accident = get_object_or_404(AccidentRecord, id=accident_id)
    accident.delete()
    messages.success(request, "Accident supprimé.")
    return redirect('dashboard_accidents')


@staff_required
def dashboard_parts(request):
    parts = SparePartRecord.objects.select_related('car_unit', 'car_unit__car_model', 'maintenance').all()
    return render(request, 'dashboard/parts_list.html', {'parts': parts})


@staff_required
def dashboard_part_add(request):
    form = SparePartForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        part = form.save()

        if part.total > 0:
            FinanceEntry.objects.create(
                titre=f"Pièce - {part.nom_piece}",
                operation_type='piece',
                montant=part.total,
                date=part.date,
                tiers_nom=part.fournisseur,
                car_model=part.car_unit.car_model,
                car_unit=part.car_unit,
                note=part.description
            )

        messages.success(request, "Pièce ajoutée.")
        return redirect('dashboard_parts')

    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Ajouter pièce'})


@staff_required
def dashboard_part_edit(request, part_id):
    part = get_object_or_404(SparePartRecord, id=part_id)
    form = SparePartForm(request.POST or None, instance=part)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Pièce modifiée.")
        return redirect('dashboard_parts')
    return render(request, 'dashboard/simple_form.html', {'form': form, 'title': 'Modifier pièce'})


@staff_required
def dashboard_part_delete(request, part_id):
    part = get_object_or_404(SparePartRecord, id=part_id)
    part.delete()
    messages.success(request, "Pièce supprimée.")
    return redirect('dashboard_parts')
def get_paypal_access_token():
    auth = f"{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}"
    encoded_auth = base64.b64encode(auth.encode()).decode()

    response = requests.post(
        f"{settings.PAYPAL_BASE_URL}/v1/oauth2/token",
        headers={
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]@staff_required
def dashboard_booking_control(request):
    settings_obj = SiteSetting.load()

    control_form = BookingControlForm(
        request.POST or None,
        instance=settings_obj,
        prefix='control'
    )

    manual_form = AdminManualReservationForm(
        request.POST or None,
        prefix='manual'
    )

    block_form = AdminCarBlockForm(
        request.POST or None,
        prefix='block'
    )

    if request.method == 'POST':
        if 'save_controls' in request.POST:
            if control_form.is_valid():
                control = control_form.save(commit=False)
                control.pk = 1
                control.save()
                messages.success(request, "Paramètres de réservation mis à jour.")
                return redirect('dashboard_booking_control')

        elif 'save_manual_reservation' in request.POST:
            if manual_form.is_valid():
                car_model = manual_form.cleaned_data['car_model']
                requested_transmission = manual_form.cleaned_data['requested_transmission']
                date_debut = manual_form.cleaned_data['date_debut']
                date_fin = manual_form.cleaned_data['date_fin']

                if date_fin < date_debut:
                    messages.error(request, "La date de fin doit être après la date de début.")
                elif check_reservation_conflict(car_model, date_debut, date_fin, requested_transmission):
                    messages.error(request, "Aucune unité disponible pour cette période.")
                else:
                    units = get_available_units(car_model, date_debut, date_fin, requested_transmission)
                    if not units:
                        messages.error(request, "Aucune unité trouvée.")
                    else:
                        unit = units[0]

                        reservation = Reservation(
                            car_model=car_model,
                            car_unit=unit,
                            requested_transmission=requested_transmission,
                            nom_complet=manual_form.cleaned_data['nom_complet'],
                            email=manual_form.cleaned_data['email'],
                            telephone=manual_form.cleaned_data['telephone'],
                            adresse=manual_form.cleaned_data['adresse'],
                            cin=manual_form.cleaned_data['cin'],
                            numero_permis=manual_form.cleaned_data['numero_permis'],
                            date_debut=date_debut,
                            date_fin=date_fin,
                            type_reservation='normale',
                            statut=manual_form.cleaned_data['statut'],
                            kilometrage_depart=unit.kilometrage_actuel,
                            est_annulable=False,
                        )

                        if hasattr(reservation, 'prix_par_jour_capture'):
                            if hasattr(car_model, 'get_price_for_days'):
                                jours = (date_fin - date_debut).days + 1
                                reservation.prix_par_jour_capture = car_model.get_price_for_days(jours)
                            else:
                                reservation.prix_par_jour_capture = car_model.prix_final

                        reservation.save()
                        messages.success(request, "Réservation manuelle créée avec succès.")
                        return redirect('dashboard_booking_control')

        elif 'save_block_period' in request.POST:
            if block_form.is_valid():
                block = block_form.save(commit=False)

                if block.date_fin < block.date_debut:
                    messages.error(request, "La date de fin doit être après la date de début.")
                else:
                    block.created_by = request.user
                    block.save()
                    messages.success(request, "Période bloquée avec succès.")
                    return redirect('dashboard_booking_control')

    recent_manual_reservations = Reservation.objects.filter(
        user__isnull=True
    ).select_related('car_model', 'car_unit').order_by('-created_at')[:10]

    recent_blocks = CarBlockPeriod.objects.select_related(
        'car_model', 'car_unit'
    ).filter(actif=True).order_by('-created_at')[:10]

    return render(request, 'dashboard/booking_control.html', {
        'control_form': control_form,
        'manual_form': manual_form,
        'block_form': block_form,
        'settings_obj': settings_obj,
        'recent_manual_reservations': recent_manual_reservations,
        'recent_blocks': recent_blocks,
    })