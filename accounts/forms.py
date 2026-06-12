from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import SiteConfiguration, User


class UserRegisterForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "full_name",
            "email",
            "phone",
            "sex",
            "musical_genre",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({
                "class": "form-control"
            })


class SiteConfigurationForm(forms.ModelForm):
    class Meta:
        model = SiteConfiguration
        fields = (
            "site_name",
            "hero_subtitle",
            "allow_registration",
            "maintenance_message",
        )
        widgets = {
            "site_name": forms.TextInput(attrs={"class": "form-control"}),
            "hero_subtitle": forms.TextInput(attrs={"class": "form-control"}),
            "allow_registration": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "maintenance_message": forms.TextInput(attrs={"class": "form-control"}),
        }
