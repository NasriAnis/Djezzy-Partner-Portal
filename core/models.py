from django.db import models
from django.utils.text import slugify
from django.core.validators import MinValueValidator, MaxValueValidator

from shared.models import WILAYA_CHOICES

"""
Models setup:
    OfferCategory (e.g. "Offres Internet")
    └── Offer (e.g. "Djezzy 3Ayla")
        ├── OfferPlan (15Go / 8500 DA)
        ├── OfferPlan (60Go / 9000 DA)
        └── OfferPlan (150Go / 9990 DA)
"""


class OfferCategory(models.Model):
    """eg Offres Prépayées, Offres Internet, Roaming Europe"""

    name = models.CharField(max_length=20, unique=True)
    order = models.PositiveIntegerField(default=0)

    # ordering purpose
    class Meta:
        verbose_name_plural = "Offer categories"
        ordering = ["order"]

    # adding labels for admin panel
    def __str__(self):
        return self.name


class Offer(models.Model):
    """eg Djezzy 3Ayla, DjezzyNet, Nouveau Modem 5G"""

    category = models.ForeignKey(
        OfferCategory, on_delete=models.CASCADE, related_name="offers"
    )
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to="offers/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_new = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Quota Helper Methods
    def get_quota_for_wilaya(self, wilaya_code):
        padded_code = str(wilaya_code).zfill(2)
        return self.wilaya_quotas.filter(wilaya_code=padded_code).first()

    def has_available_quota(self, wilaya_code, quantity=1):
        quota = self.get_quota_for_wilaya(wilaya_code)
        if not quota:
            return False  # No quota record created for this Wilaya
        return quota.is_available(quantity)

    # ordering purpose
    class Meta:
        ordering = ["category", "title"]

    # auto slugify if empty
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    # adding labels for admin panel
    def __str__(self):
        return self.title


class OfferPlan(models.Model):
    """Pricing tiers within an offer, eg 15Go/8500DA, 60Go/9000DA, 150Go/9990DA"""

    offer = models.ForeignKey(Offer, on_delete=models.CASCADE, related_name="plans")
    label = models.CharField(max_length=50, blank=True)  # "15Go", "60Go"
    data_amount_gb = models.PositiveIntegerField(null=True, blank=True)
    price_da = models.DecimalField(max_digits=10, decimal_places=2)
    validity_days = models.PositiveIntegerField(default=30)

    # other config can be set via json dynamically
    features = models.JSONField(default=dict, blank=True)

    # ordering purpose
    class Meta:
        ordering = ["price_da"]

    @property
    def features_pretty(self):
        """Pretty-printed JSON string of `features`, for editable textareas."""
        import json

        try:
            return json.dumps(self.features or {}, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            return "{}"

    # adding labels for admin panel
    def __str__(self):
        return f"{self.offer.title} — {self.label or self.data_amount_gb}Go — {self.price_da} DA"


class OfferQuota(models.Model):
    offer = models.ForeignKey(
        Offer, on_delete=models.CASCADE, related_name="wilaya_quotas"
    )
    wilaya_code = models.CharField(max_length=2, choices=WILAYA_CHOICES)
    total_quota = models.PositiveIntegerField(
        help_text="Total units available for this Wilaya"
    )
    allocated_quota = models.PositiveIntegerField(
        default=0, help_text="Units currently assigned to stores/clients"
    )
    percentage_by_client = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Max %% of total_quota a single store/client can hold for this offer. 0 = no per-client cap.",
    )

    class Meta:
        verbose_name = "Offer Wilaya Quota"
        verbose_name_plural = "Offer Wilaya Quotas"
        unique_together = ("offer", "wilaya_code")
        indexes = [
            models.Index(fields=["offer", "wilaya_code"]),
        ]

    @property
    def remaining_quota(self):
        return max(0, self.total_quota - self.allocated_quota)

    def is_available(self, quantity=1):
        return self.remaining_quota >= quantity

    @property
    def max_quantity_per_client(self):
        """Absolute unit cap for one store, derived from percentage_by_client."""
        return int(self.total_quota * self.percentage_by_client / 100)

    def quantity_used_by(self, store):
        """Units this store already holds (draft + pending + approved) for this offer."""
        from django.db.models import Sum
        from clients.models import StoreOfferTransaction

        total = (
            StoreOfferTransaction.objects.filter(
                from_quota=self,
                store=store,
                plan__offer=self.offer,
            )
            .exclude(status=StoreOfferTransaction.STATUS_BLOCKED)
            .exclude(status=StoreOfferTransaction.STATUS_WAITLISTED)
            .aggregate(total=Sum("quantity_bought"))["total"]
        )
        return total or 0

    def remaining_for_store(self, store):
        """
        How many more units this store can still request.
        percentage_by_client == 0 means "no per-client cap" — falls back to remaining_quota.
        """
        if not self.percentage_by_client:
            return self.remaining_quota
        used = self.quantity_used_by(store)
        return max(0, min(self.max_quantity_per_client - used, self.remaining_quota))

    def process_waitlist(self):
        from clients.models import StoreOfferTransaction, StoreStock
        from django.db.models import F

        if self.remaining_quota <= 0:
            return

        waitlisted = (
            StoreOfferTransaction.objects.select_for_update()
            .filter(
                plan__offer=self.offer,
                status=StoreOfferTransaction.STATUS_WAITLISTED,
                store__wilaya=self.wilaya_code,
            )
            .order_by("created_at")
        )

        for tx in waitlisted:
            if self.remaining_quota <= 0:
                break

            available = min(self.remaining_quota, self.remaining_for_store(tx.store))
            if available <= 0:
                continue

            approved_qty = min(tx.quantity_bought, available)

            stock_obj, created = StoreStock.objects.select_for_update().get_or_create(
                store=tx.store, plan=tx.plan, defaults={"stock": approved_qty}
            )
            if not created:
                stock_obj.stock = F("stock") + approved_qty
                stock_obj.save(update_fields=["stock"])

            if tx.quantity_bought <= available:
                tx.status = StoreOfferTransaction.STATUS_APPROVED
                tx.save(update_fields=["status"])
            else:
                StoreOfferTransaction.objects.create(
                    store=tx.store,
                    plan=tx.plan,
                    quantity_bought=approved_qty,
                    status=StoreOfferTransaction.STATUS_APPROVED,
                )
                tx.quantity_bought -= approved_qty
                tx.save(update_fields=["quantity_bought"])

            self.allocated_quota += approved_qty
            self.save(update_fields=["allocated_quota"])

    def __str__(self):
        return f"{self.offer.title} - {self.get_wilaya_code_display()}: {self.remaining_quota}/{self.total_quota} left"
