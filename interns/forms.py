from django import forms
from django.contrib.auth import get_user_model
from core.models import OfferCategory, Offer, OfferPlan, OfferQuota, WILAYA_CHOICES

from .models import Commercial

User = get_user_model()


# Login commercial form at /commercial/login/
class CommercialAdminForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()
    password = forms.CharField(
        widget=forms.PasswordInput,
        required=False,
        help_text="Leave blank to keep existing password when editing.",
    )

    class Meta:
        model = Commercial
        fields = ["phone", "access_rights", "modifications_rights"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name
            self.fields["email"].initial = self.instance.user.email
            self.fields["password"].required = False

    def save(self, commit=True):
        commercial = super().save(commit=False)

        if self.instance.pk:
            user = self.instance.user
        else:
            user = User()

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]

        password = self.cleaned_data.get("password")
        if password:
            user.set_password(password)

        user.save()
        commercial.user = user

        if commit:
            commercial.save()
        return commercial


# Adding a category form at /commercial/offers/
class OfferCategoryForm(forms.ModelForm):
    class Meta:
        model = OfferCategory
        fields = ["name", "order"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Offres PostPayee"}
            ),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
        }


# Adding a Offer form at /commercial/offers/
class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ["category", "title", "description", "image", "is_active", "is_new"]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select"}),
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "image": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_new": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


# Adding a Offer Plan form at /commercial/offers/<offer-slug>/edit/
class OfferPlanForm(forms.ModelForm):
    class Meta:
        model = OfferPlan
        fields = ["label", "data_amount_gb", "price_da", "validity_days", "features"]
        widgets = {
            "label": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. 60Go"}
            ),
            "data_amount_gb": forms.NumberInput(attrs={"class": "form-control"}),
            "price_da": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "validity_days": forms.NumberInput(attrs={"class": "form-control"}),
            "features": forms.Textarea(
                attrs={"class": "form-control font-monospace", "rows": 4}
            ),
        }


# Adding a Offer Plan Quota form at /commercial/offers/<offer-slug>/edit/
class OfferQuotaForm(forms.ModelForm):
    class Meta:
        model = OfferQuota
        fields = ["wilaya_code", "total_quota", "percentage_by_client"]
        widgets = {
            "wilaya_code": forms.Select(
                choices=WILAYA_CHOICES, attrs={"class": "form-select"}
            ),
            "total_quota": forms.NumberInput(attrs={"class": "form-control"}),
            "percentage_by_client": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 0,
                    "max": 100,
                    "step": "0.01",
                    "placeholder": "0 = no per-client cap",
                }
            ),
        }
        labels = {
            "percentage_by_client": "Max %% per client (0 = no cap)",
        }
