from django import forms
from django.contrib.auth.models import User
from .models import Store, Commune

class ClientSignupForm(forms.Form):
    username = forms.CharField(max_length=30)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirm = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password') != cleaned_data.get('password_confirm'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data

class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'address_line1', 'wilaya', 'comune', 'phone', 'rc', 'nif']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Store name'}),
            'address_line1': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Address'}),
            'wilaya': forms.Select(attrs={'class': 'form-select', 'id': 'id_wilaya'}),
            'comune': forms.Select(attrs={'class': 'form-select', 'id': 'id_comune'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone (optional)'}),
            'rc': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'nif': forms.TextInput(attrs={'class': 'form-control'})
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        wilaya_code = None
        if self.is_bound:
            wilaya_code = self.data.get('wilaya')
        elif self.instance and self.instance.pk:
            wilaya_code = self.instance.wilaya
        if wilaya_code:
            padded_code = str(wilaya_code).zfill(2)
            self.fields['comune'].queryset = Commune.objects.filter(wilaya_code=padded_code).order_by('name')
        else:
            self.fields['comune'].queryset = Commune.objects.none()