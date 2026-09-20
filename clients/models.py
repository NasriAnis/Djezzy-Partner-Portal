from django.db import models
from django.contrib.auth.models import User
from django.db.models.deletion import PROTECT, SET_NULL
from core.models import OfferPlan
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from interns.models import Commercial

WILAYA_CHOICES = [
    ("01", "Adrar"),
    ("02", "Chlef"),
    ("03", "Laghouat"),
    ("04", "Oum El Bouaghi"),
    ("05", "Batna"),
    ("06", "Béjaïa"),
    ("07", "Biskra"),
    ("08", "Béchar"),
    ("09", "Blida"),
    ("10", "Bouira"),
    ("11", "Tamanrasset"),
    ("12", "Tébessa"),
    ("13", "Tlemcen"),
    ("14", "Tiaret"),
    ("15", "Tizi Ouzou"),
    ("16", "Alger"),
    ("17", "Djelfa"),
    ("18", "Jijel"),
    ("19", "Sétif"),
    ("20", "Saïda"),
    ("21", "Skikda"),
    ("22", "Sidi Bel Abbès"),
    ("23", "Annaba"),
    ("24", "Guelma"),
    ("25", "Constantine"),
    ("26", "Médéa"),
    ("27", "Mostaganem"),
    ("28", "M'Sila"),
    ("29", "Mascara"),
    ("30", "Ouargla"),
    ("31", "Oran"),
    ("32", "El Bayadh"),
    ("33", "Illizi"),
    ("34", "Bordj Bou Arréridj"),
    ("35", "Boumerdès"),
    ("36", "El Tarf"),
    ("37", "Tindouf"),
    ("38", "Tissemsilt"),
    ("39", "El Oued"),
    ("40", "Khenchela"),
    ("41", "Souk Ahras"),
    ("42", "Tipaza"),
    ("43", "Mila"),
    ("44", "Aïn Defla"),
    ("45", "Naâma"),
    ("46", "Aïn Témouchent"),
    ("47", "Ghardaïa"),
    ("48", "Relizane"),
    ("49", "Timimoun"),
    ("50", "Bordj Badji Mokhtar"),
    ("51", "Ouled Djellal"),
    ("52", "Béni Abbès"),
    ("53", "In Salah"),
    ("54", "In Guezzam"),
    ("55", "Touggourt"),
    ("56", "Djanet"),
    ("57", "El M'Ghair"),
    ("58", "El Meniaa"),
]


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
            from .services import get_least_loaded_commercial

            self.commmercial = get_least_loaded_commercial()
        super().save(*args, **kwargs)


class StoreOfferTransaction(models.Model):
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="transactions"
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
        (STATUS_WAITLISTED, "En attente de réapprovisionnement"),
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
