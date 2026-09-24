from django.db import models
from django.contrib.auth.models import User
from django.db.models.deletion import PROTECT, SET_NULL
from core.models import OfferPlan, OfferQuota
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from interns.models import Commercial
from shared.models import WILAYA_CHOICES


class Client(models.Model):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="client_profile"
    )
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self) -> str:
        return f"{self.user.first_name} {self.user.last_name}"


class Commune(models.Model):
    wilaya_code = models.CharField(max_length=2, choices=WILAYA_CHOICES, db_index=True)
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name = "Commune"
        verbose_name_plural = "Communes"
        indexes = [models.Index(fields=["wilaya_code", "name"])]

    def __str__(self):
        return f"{self.name} ({self.wilaya_code})"


class Store(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE, related_name="locations"
    )
    commmercial = models.ForeignKey(
        Commercial, on_delete=PROTECT, related_name="store", null=True
    )
    name = models.CharField(max_length=255)
    address_line1 = models.CharField(max_length=255)
    wilaya = models.CharField(max_length=2, choices=WILAYA_CHOICES)
    comune = models.ForeignKey(Commune, on_delete=models.PROTECT, related_name="stores")
    phone = models.CharField(max_length=20, blank=True)
    rc = models.ImageField(upload_to="client_rc/", default="", null=True)
    nif = models.CharField(default="", null=True, max_length=20)

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_BLOCKED = "blocked"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_BLOCKED, "Blocked"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Store"
        verbose_name_plural = "Stores"

    def __str__(self):
        return f"{self.name} ({self.client})"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.commmercial_id:
            from django.db.models import Count, Q
            from .models import Commercial, Store

            active_statuses = [Store.STATUS_PENDING, Store.STATUS_APPROVED]

            self.commerical = (
                Commercial.objects.filter(
                    manage_clients_rights=True,
                    modifications_rights=True,
                    is_active=True,
                )
                .annotate(
                    store_count=Count(
                        "store",
                        filter=Q(store__status__in=active_statuses),
                    )
                )
                .order_by("store_count", "id")
                .first()
            )

            super().save(*args, **kwargs)


class StoreOfferTransaction(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="transactions"
    )
    from_quota = models.ForeignKey(
        OfferQuota, on_delete=models.PROTECT, related_name="consumed", null=True, blank=True, default=None
    )
    plan = models.ForeignKey(
        OfferPlan, on_delete=models.PROTECT, related_name="store_transactions"
    )
    quantity_bought = models.PositiveIntegerField(default=0)

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_BLOCKED = "blocked"
    STATUS_DRAFT = "draft"
    STATUS_WAITLISTED = "waitlisted"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_BLOCKED, "Blocked"),
        (STATUS_DRAFT, "draft"),
        (STATUS_WAITLISTED, "Waitlist"),
    ]

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )

    comment = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Store Offer Transaction"
        verbose_name_plural = "Store Offer Transactions"

    def __str__(self):
        return f"{self.store.name} - {self.plan.offer.title} ({self.plan.label})"


class StoreStock(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="stock")
    plan = models.ForeignKey(
        OfferPlan, on_delete=models.PROTECT, related_name="store_stock"
    )
    stock = models.PositiveIntegerField(default=0)
    sold = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("store", "plan")

    def __str__(self):
        return f"{self.store.name} - {self.plan.offer.title} ({self.plan.label}): {self.stock} remaining"

    @property
    def remaining(self):
        return self.stock - self.sold


class OfferSale(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="sales")
    plan = models.ForeignKey(OfferPlan, on_delete=models.PROTECT, related_name="sales")
    phone_number = models.CharField(max_length=20)
    sold_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Offer Sale"
        verbose_name_plural = "Offer Sales"

    def __str__(self):
        return f"{self.store.name} sold {self.plan} to {self.phone_number}"
