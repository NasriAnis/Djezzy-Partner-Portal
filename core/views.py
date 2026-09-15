from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction

from .models import Offer, OfferPlan, OfferQuota, OfferCategory
from clients.models import Store, StoreOfferTransaction

########## Pages ##########


def client_index_page(request):
    offers = Offer.objects.filter(is_active=True)
    categories = OfferCategory.objects.all()

    selected_category = None
    category_id = request.GET.get("category")
    if category_id:
        offers = offers.filter(category_id=category_id)
        selected_category = categories.filter(id=category_id).first()

    context = {
        "offers": offers,
        "categories": categories,
        "selected_category": selected_category,
    }
    return render(request, "core/client_index.html", context)


def offer_detail_page(request, offer_slug):
    offer = get_object_or_404(Offer, slug=offer_slug, is_active=True)
    offer_plans = offer.plans.all()

    user_stores = []
    selected_store = None
    quota_info = None

    if request.user.is_authenticated and hasattr(request.user, "client_profile"):
        # Only stores that have been accepted can be selected for buying
        user_stores = request.user.client_profile.locations.filter(
            status=Store.STATUS_APPROVED
        )

        selected_store_id = request.GET.get("store_id")
        if selected_store_id:
            selected_store = user_stores.filter(id=selected_store_id).first()
        else:
            selected_store = user_stores.first()

        if selected_store:
            formatted_wilaya_code = str(selected_store.wilaya).zfill(2)
            quota_info = OfferQuota.objects.filter(
                offer=offer, wilaya_code=formatted_wilaya_code
            ).first()

    # Form handling for custom quantity purchases
    if request.method == "POST":
        if not request.user.is_authenticated or not selected_store:
            messages.error(
                request, "You must select a valid, accepted store to place an order."
            )
            return redirect("offer_detail_page", offer_slug=offer.slug)

        if selected_store.status != Store.STATUS_APPROVED:
            messages.error(
                request, "This store isn't approved yet — purchases aren't allowed."
            )
            return redirect("offer_detail_page", offer_slug=offer.slug)

        plan_id = request.POST.get("plan_id")
        plan = get_object_or_404(OfferPlan, id=plan_id, offer=offer)
        intent = request.POST.get("intent")  # "draft" or "buy_now"

        try:
            quantity = int(request.POST.get("quantity", 1))
            if quantity < 1:
                raise ValueError
        except ValueError:
            messages.error(request, "Please enter a valid quantity of at least 1.")
            return redirect("offer_detail_page", offer_slug=offer.slug)

        formatted_wilaya_code = str(selected_store.wilaya).zfill(2)

        if intent == "draft":
            # Cart-style: no quota deducted yet, just a rough sanity check
            already_in_cart = StoreOfferTransaction.objects.filter(
                store=selected_store,
                plan=plan,
                status=StoreOfferTransaction.STATUS_DRAFT,
            ).first()
            existing_qty = already_in_cart.quantity_bought if already_in_cart else 0

            current_quota = OfferQuota.objects.filter(
                offer=offer, wilaya_code=formatted_wilaya_code
            ).first()

            if not current_quota or not current_quota.is_available(existing_qty + quantity):
                available = current_quota.remaining_quota if current_quota else 0
                messages.error(
                    request,
                    f"Can't add {quantity} — only {available} remaining for your Wilaya.",
                )
                return redirect("offer_detail_page", offer_slug=offer.slug)

            with transaction.atomic():
                store_tx, created = StoreOfferTransaction.objects.get_or_create(
                    store=selected_store,
                    plan=plan,
                    status=StoreOfferTransaction.STATUS_DRAFT,
                    defaults={"quantity_bought": quantity},
                )
                if not created:
                    store_tx.quantity_bought += quantity
                    store_tx.save()

            messages.success(
                request,
                f"Added {quantity}x '{plan.label}' to your draft order for {selected_store.name}.",
            )
            return redirect("offer_detail_page", offer_slug=offer.slug)

        else:
            # Direct buy: deduct quota immediately, goes straight to pending
            with transaction.atomic():
                current_quota = (
                    OfferQuota.objects.select_for_update()
                    .filter(offer=offer, wilaya_code=formatted_wilaya_code)
                    .first()
                )

                if current_quota and current_quota.is_available(quantity):
                    store_tx, created = StoreOfferTransaction.objects.get_or_create(
                        store=selected_store,
                        plan=plan,
                        status=StoreOfferTransaction.STATUS_PENDING,
                        defaults={"quantity_bought": quantity},
                    )
                    if not created:
                        store_tx.quantity_bought += quantity
                        store_tx.save()

                    current_quota.allocated_quota += quantity
                    current_quota.save()

                    messages.success(
                        request,
                        f"Successfully purchased {quantity}x '{plan.label}' for {selected_store.name}!",
                    )
                    return redirect("offer_detail_page", offer_slug=offer.slug)
                else:
                    available = current_quota.remaining_quota if current_quota else 0
                    messages.error(
                        request,
                        f"Order failed. Requested {quantity} units, but only {available} remaining for your Wilaya.",
                    )
    context = {
        "offer": offer,
        "offer_plans": offer_plans,
        "user_stores": user_stores,
        "selected_store": selected_store,
        "quota_info": quota_info,
    }
    return render(request, "core/offer_details_page.html", context)
