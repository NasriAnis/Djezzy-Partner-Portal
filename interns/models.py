from django.conf import settings
from django.db import models


class Commercial(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commercial_profile",
    )
    phone = models.DecimalField(max_digits=10, decimal_places=0, unique=True)
    manage_clients_rights = models.BooleanField(default=True)
    manage_offers_rights = models.BooleanField(default=True)
    has_access_to_all = models.BooleanField(default=False)
    modifications_rights = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.has_access_to_all:
            self.manage_clients_rights = True
            self.manage_offers_rights = True

    def __str__(self) -> str:
        return f"{self.user.first_name} {self.user.last_name}"
