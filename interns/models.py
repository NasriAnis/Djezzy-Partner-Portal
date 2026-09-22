from django.conf import settings
from django.db import models


class Commercial(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="commercial_profile",
    )
    phone = models.DecimalField(max_digits=10, decimal_places=0, unique=True)

    class AccessRights(models.TextChoices):
        MANAGE_CLIENTS = "MC", "Manage Clients"
        MANAGE_OFFERS = "MO", "Manage Offers"
        MANAGE_ALL = "MA", "Manage All"

    access_rights = models.CharField(
        max_length=2,
        choices=AccessRights.choices,
    )
    modifications_rights = models.BooleanField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.user.first_name} {self.user.last_name}"
