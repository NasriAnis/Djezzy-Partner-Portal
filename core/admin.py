from django.contrib import admin

from .models import OfferCategory, Offer, OfferPlan, OfferQuota

admin.site.register(OfferCategory)
admin.site.register(Offer)
admin.site.register(OfferPlan)
admin.site.register(OfferQuota)
