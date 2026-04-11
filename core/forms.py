from django import forms
from django import forms
from .models import SiteSetting, Reservation, CarModel
from django.contrib.auth.models import User
from .models import (
    Reservation, CarModel, CarUnit, CarImage, Client,
    FinanceEntry, MaintenanceRecord, AccidentRecord, SparePartRecord
)


class PrettyModelForm(forms.ModelForm):
    def _init_(self, *args, **kwargs):
        super()._init_(*args, **kwargs)
        for _, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                css = 'form-check-input'
            elif isinstance(field.widget, forms.Select):
                css = 'form-select'
            else:
                css = 'form-control'
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} {css}".strip()


class SignUpForm(PrettyModelForm):
    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    username = forms.CharField(label="Nom d'utilisateur", max_length=150)
    email = forms.EmailField(label="Email")
    telephone = forms.CharField(label="Téléphone", max_length=20)
    adresse = forms.CharField(label="Adresse", required=False)
    cin = forms.CharField(label="CIN", required=False)
    numero_permis = forms.CharField(label="Numéro permis", required=False)
    password1 = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirmer mot de passe", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email']

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password1') != cleaned.get('password2'):
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.set_password(self.cleaned_data['password1'])

        if commit:
            user.save()
            Client.objects.create(
                linked_user=user,
                nom=self.cleaned_data['last_name'],
                prenom=self.cleaned_data['first_name'],
                telephone=self.cleaned_data['telephone'],
                email=self.cleaned_data['email'],
                adresse=self.cleaned_data.get('adresse', ''),
                cin=self.cleaned_data.get('cin', ''),
                numero_permis=self.cleaned_data.get('numero_permis', ''),
            )
        return user


class LoginForm(forms.Form):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )


class SearchAvailabilityForm(forms.Form):
    transmission = forms.ChoiceField(
        required=False,
        choices=[('', 'Toutes'), ('manuelle', 'Manuelle'), ('automatique', 'Automatique')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control flatpickr-input',
            'placeholder': 'Date de début'
        })
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control flatpickr-input',
            'placeholder': 'Date de fin'
        })
    )


class ReservationNormalForm(PrettyModelForm):
    class Meta:
        model = Reservation
        fields = [
            'requested_transmission',
            'nom_complet',
            'email',
            'telephone',
            'adresse',
            'cin',
            'numero_permis',
            'date_debut',
            'date_fin'
        ]
        widgets = {
            'date_debut': forms.TextInput(attrs={'class': 'form-control flatpickr-input'}),
            'date_fin': forms.TextInput(attrs={'class': 'form-control flatpickr-input'}),
            'adresse': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Rabat centre, Casa, Aéroport Salé...'
            }),
        }
        labels = {
            'adresse': 'Adresse souhaitée de livraison',
            'nom_complet': 'Nom complet',
            'telephone': 'Téléphone',
            'cin': 'CIN',
            'numero_permis': 'Numéro de permis',
            'date_debut': 'Date de début',
            'date_fin': 'Date de fin',
        }

class ReservationCompleteForm(PrettyModelForm):
    class Meta:
        model = Reservation
        fields = ['requested_transmission', 'date_debut', 'date_fin']
        widgets = {
            'date_debut': forms.TextInput(attrs={'class': 'form-control flatpickr-input'}),
            'date_fin': forms.TextInput(attrs={'class': 'form-control flatpickr-input'}),
        }


class CarModelForm(PrettyModelForm):
    class Meta:
        model = CarModel
        fields = [
            'marque', 'modele', 'annee', 'nombre_places',
            'prix_par_jour', 'reduction_active', 'reduction_pourcentage',
            'description', 'image_principale', 'actif'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
        }


class CarUnitForm(PrettyModelForm):
    class Meta:
        model = CarUnit
        fields = [
            'car_model', 'nom_interne', 'immatriculation', 'transmission',
            'carburant', 'couleur', 'kilometrage_actuel',
            'date_prochain_entretien', 'notes_admin', 'active'
        ]
        widgets = {
            'date_prochain_entretien': forms.DateInput(attrs={'type': 'date'}),
            'notes_admin': forms.Textarea(attrs={'rows': 3}),
        }


class CarImageForm(PrettyModelForm):
    class Meta:
        model = CarImage
        fields = ['image', 'type_image', 'titre']


class ClientForm(PrettyModelForm):
    class Meta:
        model = Client
        fields = [
            'nom', 'prenom', 'telephone', 'email', 'adresse',
            'cin', 'numero_permis', 'date_expiration_permis', 'notes'
        ]
        widgets = {
            'date_expiration_permis': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class ReservationAdminForm(PrettyModelForm):
    class Meta:
        model = Reservation
        fields = [
            'car_model', 'car_unit', 'client', 'type_reservation', 'statut',
            'requested_transmission', 'nom_complet', 'email', 'telephone',
            'adresse', 'cin', 'numero_permis', 'date_debut', 'date_fin',
            'kilometrage_depart', 'kilometrage_retour', 'caution', 'avance',
            'notes_admin'
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'type': 'date'}),
            'notes_admin': forms.Textarea(attrs={'rows': 3}),
        }
class QuickFinanceForm(PrettyModelForm):
    class Meta:
        model = FinanceEntry
        fields = [
            'titre',
            'categorie_libre',
            'montant',
            'date',
            'tiers_nom',
            'reference',
            'note',
            'car_model',
            'car_unit',
            'client',
            'reservation',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'note': forms.Textarea(attrs={'rows': 3}),
        }

    def _init_(self, *args, **kwargs):
        operation_type = kwargs.pop('operation_type', None)
        super()._init_(*args, **kwargs)

        self.operation_type = operation_type

        for field_name in self.fields:
            self.fields[field_name].required = False

        self.fields['titre'].required = True
        self.fields['montant'].required = True
        self.fields['date'].required = True


class MaintenanceForm(PrettyModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = [
            'car_unit', 'titre', 'date_entretien', 'kilometrage', 'cout',
            'prochain_entretien_date', 'prochain_entretien_km', 'description'
        ]
        widgets = {
            'date_entretien': forms.DateInput(attrs={'type': 'date'}),
            'prochain_entretien_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class AccidentForm(PrettyModelForm):
    class Meta:
        model = AccidentRecord
        fields = [
            'car_unit', 'reservation', 'date_accident', 'titre',
            'description', 'cout_estime', 'montant_assurance',
            'montant_restant', 'statut'
        ]
        widgets = {
            'date_accident': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class SparePartForm(PrettyModelForm):
    class Meta:
        model = SparePartRecord
        fields = [
            'car_unit', 'maintenance', 'nom_piece', 'quantite',
            'prix_unitaire', 'date', 'fournisseur', 'description'
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }
class BookingControlForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ['allow_normal_booking', 'allow_online_payment']
        labels = {
            'allow_normal_booking': 'Autoriser réservation normale',
            'allow_online_payment': 'Autoriser paiement en ligne',
        }


class AdminManualReservationForm(forms.Form):
    car_model = forms.ModelChoiceField(
        queryset=CarModel.objects.filter(actif=True),
        label="Voiture"
    )
    requested_transmission = forms.ChoiceField(
        choices=[
            ('', 'Transmission non imposée'),
            ('manuelle', 'Manuelle'),
            ('automatique', 'Automatique'),
        ],
        required=False,
        label="Transmission souhaitée"
    )

    nom_complet = forms.CharField(max_length=150, label="Nom complet")
    email = forms.EmailField(required=False, label="Email")
    telephone = forms.CharField(max_length=30, label="Téléphone")
    adresse = forms.CharField(max_length=255, required=False, label="Adresse / lieu de livraison")
    cin = forms.CharField(max_length=50, required=False, label="CIN")
    numero_permis = forms.CharField(max_length=100, required=False, label="Numéro de permis")

    date_debut = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date début")
    date_fin = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label="Date fin")

    statut = forms.ChoiceField(
        choices=[
            ('confirmee', 'Confirmée'),
            ('en_attente', 'En attente'),
        ],
        initial='confirmee',
        label="Statut"
    )