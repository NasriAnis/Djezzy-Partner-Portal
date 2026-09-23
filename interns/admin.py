from django.contrib import admin
from .models import Commercial
from .forms import CommercialAdminForm


@admin.register(Commercial)
class CommercialAdmin(admin.ModelAdmin):
    form = CommercialAdminForm
    list_display = (
        "user",
        "phone",
        "manage_clients_rights",
        "manage_offers_rights",
        "has_access_to_all",
        "modifications_rights",
        "created_at",
    )

    def user(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
