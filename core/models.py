from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User


ACTIVE_RESERVATION_STATUSES = [
    'en_attente',
    'confirmee',
    'en_cours',
    'payee',
]


class CarModel(models.Model):
    marque = models.CharField(max_length=100)
    modele = models.CharField(max_length=100)
    annee = models.PositiveIntegerField()
    nombre_places = models.PositiveIntegerField(default=5)

    prix_par_jour = models.DecimalField(max_digits=10, decimal_places=2)
    reduction_active = models.BooleanField(default=False)
    reduction_pourcentage = models.PositiveIntegerField(default=0)

    description = models.TextField()
    image_principale = models.ImageField(upload_to='cars/main/')
    actif = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.marque} {self.modele}"

    @property
    def prix_final(self):
        if self.reduction_active and self.reduction_pourcentage > 0:
            reduction = (Decimal(self.reduction_pourcentage) / Decimal('100')) * self.prix_par_jour
            return self.prix_par_jour - reduction
        return self.prix_par_jour

    def get_available_units(self, date_debut=None, date_fin=None, requested_transmission=''):
        units = self.units.filter(active=True)

        if requested_transmission:
            units = units.filter(transmission=requested_transmission)

        if not date_debut or not date_fin:
            return list(units)

        available = []
        for unit in units:
            conflict = unit.reservations.filter(
                statut__in=ACTIVE_RESERVATION_STATUSES,
                date_debut__lte=date_fin,
                date_fin__gte=date_debut
            ).exists()
            if not conflict:
                available.append(unit)
        return available

    def available_units_count(self, date_debut=None, date_fin=None, requested_transmission=''):
        return len(self.get_available_units(date_debut, date_fin, requested_transmission))

    def available_transmissions(self):
        return list(
            self.units.filter(active=True)
            .values_list('transmission', flat=True)
            .distinct()
        )


class CarImage(models.Model):
    TYPE_CHOICES = [
        ('exterieur', 'Extérieur'),
        ('interieur', 'Intérieur'),
        ('salon', 'Salon'),
        ('pneus', 'Pneus'),
        ('moteur', 'Moteur'),
        ('autre', 'Autre'),
    ]

    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='cars/gallery/')
    type_image = models.CharField(max_length=20, choices=TYPE_CHOICES, default='autre')
    titre = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.car_model} - {self.type_image}"


class CarUnit(models.Model):
    TRANSMISSION_CHOICES = [
        ('manuelle', 'Manuelle'),
        ('automatique', 'Automatique'),
    ]

    FUEL_CHOICES = [
        ('diesel', 'Diesel'),
        ('essence', 'Essence'),
        ('hybride', 'Hybride'),
        ('electrique', 'Électrique'),
    ]

    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE, related_name='units')
    nom_interne = models.CharField(max_length=100, blank=True)
    immatriculation = models.CharField(max_length=50, unique=True)
    transmission = models.CharField(max_length=20, choices=TRANSMISSION_CHOICES)
    carburant = models.CharField(max_length=20, choices=FUEL_CHOICES)
    couleur = models.CharField(max_length=50)

    kilometrage_actuel = models.PositiveIntegerField(default=0)
    date_prochain_entretien = models.DateField(null=True, blank=True)
    notes_admin = models.TextField(blank=True)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['car_model__marque', 'car_model__modele', 'immatriculation']

    def __str__(self):
        return f"{self.car_model} - {self.immatriculation}"

    def is_available_for_period(self, date_debut, date_fin, exclude_reservation_id=None):
        qs = self.reservations.filter(
            statut__in=ACTIVE_RESERVATION_STATUSES,
            date_debut__lte=date_fin,
            date_fin__gte=date_debut
        )
        if exclude_reservation_id:
            qs = qs.exclude(id=exclude_reservation_id)
        return not qs.exists()


class Client(models.Model):
    linked_user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='client_profile'
    )
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    adresse = models.CharField(max_length=255, blank=True)
    cin = models.CharField(max_length=50, blank=True)
    numero_permis = models.CharField(max_length=100, blank=True)
    date_expiration_permis = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.nom} {self.prenom}"


class Reservation(models.Model):
    TYPE_CHOICES = [
        ('normale', 'Réservation normale'),
        ('complete', 'Réservation complète'),
        ('admin', 'Réservation admin'),
    ]

    STATUS_CHOICES = [
        ('en_attente', 'En attente'),
        ('confirmee', 'Confirmée'),
        ('en_cours', 'En cours'),
        ('terminee', 'Terminée'),
        ('annulee', 'Annulée'),
        ('refusee', 'Refusée'),
        ('paiement_en_attente', 'Paiement en attente'),
        ('payee', 'Payée'),
    ]

    TRANSMISSION_CHOICES = [
        ('', 'Toutes'),
        ('manuelle', 'Manuelle'),
        ('automatique', 'Automatique'),
    ]

    car_model = models.ForeignKey(CarModel, on_delete=models.CASCADE, related_name='reservations')
    car_unit = models.ForeignKey(
        CarUnit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations'
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reservations'
    )

    type_reservation = models.CharField(max_length=20, choices=TYPE_CHOICES, default='admin')
    statut = models.CharField(max_length=30, choices=STATUS_CHOICES, default='en_attente')

    requested_transmission = models.CharField(
        max_length=20,
        choices=TRANSMISSION_CHOICES,
        blank=True,
        default=''
    )

    nom_complet = models.CharField(max_length=150)
    email = models.EmailField()
    telephone = models.CharField(max_length=20)
    adresse = models.CharField(max_length=255, blank=True)
    cin = models.CharField(max_length=50, blank=True)
    numero_permis = models.CharField(max_length=100, blank=True)

    date_debut = models.DateField()
    date_fin = models.DateField()

    kilometrage_depart = models.PositiveIntegerField(default=0)
    kilometrage_retour = models.PositiveIntegerField(null=True, blank=True)

    prix_par_jour_capture = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    caution = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    avance = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    notes_admin = models.TextField(blank=True)
    est_annulable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Réservation #{self.id} - {self.car_model}"

    def nombre_jours(self):
        delta = (self.date_fin - self.date_debut).days + 1
        return max(delta, 1)

    def calculer_total(self):
        return self.nombre_jours() * self.prix_par_jour_capture

    def save(self, *args, **kwargs):
        if not self.prix_par_jour_capture or self.prix_par_jour_capture == 0:
            self.prix_par_jour_capture = self.car_model.prix_final
        self.montant_total = self.calculer_total()
        super().save(*args, **kwargs)

    def peut_etre_annulee_par_client(self):
        return self.statut in ['en_attente', 'paiement_en_attente'] and self.est_annulable

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    reservation = models.OneToOneField(Reservation, on_delete=models.CASCADE, related_name='payment')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    provider = models.CharField(max_length=50, default='demo')
    transaction_id = models.CharField(max_length=150, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def _str_(self):
        return f"Paiement {self.reservation_id}"

class FinanceEntry(models.Model):
    OPERATION_CHOICES = [
        ('charge_simple', 'Charge simple'),
        ('revenu_simple', 'Revenu simple'),
        ('salaire', 'Salaire'),
        ('loyer', 'Loyer'),
        ('credit_recu', 'Crédit reçu'),
        ('remboursement_credit', 'Remboursement crédit'),
        ('avance_recue', 'Avance reçue'),
        ('avance_versee', 'Avance versée'),
        ('capital', 'Apport en capital'),
        ('retrait', 'Retrait'),
        ('entretien', 'Entretien'),
        ('carburant', 'Carburant'),
        ('piece', 'Pièce de rechange'),
        ('accident', 'Accident'),
        ('location', 'Paiement location'),
        ('autre', 'Autre'),
    ]

    titre = models.CharField(max_length=150)
    operation_type = models.CharField(max_length=30, choices=OPERATION_CHOICES)
    categorie_libre = models.CharField(max_length=150, blank=True)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()

    tiers_nom = models.CharField(max_length=150, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    note = models.TextField(blank=True)

    car_model = models.ForeignKey(CarModel, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_entries')
    car_unit = models.ForeignKey(CarUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_entries')
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_entries')
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='finance_entries')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']

    def _str_(self):
        return f"{self.titre} - {self.montant} DH"

    @property
    def is_positive(self):
        return self.operation_type in [
            'revenu_simple', 'credit_recu', 'avance_recue', 'location', 'capital'
        ]

    @property
    def signed_amount(self):
        return self.montant if self.is_positive else -self.montant

class MaintenanceRecord(models.Model):
    car_unit = models.ForeignKey(CarUnit, on_delete=models.CASCADE, related_name='maintenances')
    titre = models.CharField(max_length=150)
    date_entretien = models.DateField()
    kilometrage = models.PositiveIntegerField(default=0)
    cout = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prochain_entretien_date = models.DateField(null=True, blank=True)
    prochain_entretien_km = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date_entretien', '-id']

    def __str__(self):
        return f"{self.car_unit} - {self.titre}"


class AccidentRecord(models.Model):
    car_unit = models.ForeignKey(CarUnit, on_delete=models.CASCADE, related_name='accidents')
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='accidents')
    date_accident = models.DateField()
    titre = models.CharField(max_length=150)
    description = models.TextField()
    cout_estime = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_assurance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_restant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=100, default='En traitement')

    class Meta:
        ordering = ['-date_accident', '-id']

    def __str__(self):
        return f"{self.car_unit} - {self.titre}"


class SparePartRecord(models.Model):
    car_unit = models.ForeignKey(CarUnit, on_delete=models.CASCADE, related_name='spare_parts')
    maintenance = models.ForeignKey(MaintenanceRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='parts')
    nom_piece = models.CharField(max_length=150)
    quantite = models.PositiveIntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date = models.DateField()
    fournisseur = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.nom_piece} - {self.car_unit}"

    @property
    def total(self):
        return self.quantite * self.prix_unitaire
    
class SiteSetting(models.Model):
    allow_normal_booking = models.BooleanField(default=True)
    allow_online_payment = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def _str_(self):
        return "Paramètres du site"

    @classmethod
    def load(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return obj