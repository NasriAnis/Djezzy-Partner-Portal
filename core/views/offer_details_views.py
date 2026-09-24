from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum

from ..models import Offer, OfferPlan, OfferQuota
from clients.models import Store, StoreOfferTransaction


# ---------------------------------------------------------------------------
# Store selection
# ---------------------------------------------------------------------------

def _get_user_stores(request):
    """Approved stores belonging to the logged-in client, or an empty queryset."""
    if request.user.is_authenticated and hasattr(request.user, "client_profile"):
        return request.user.client_profile.locations.filter(
            status=Store.STATUS_APPROVED
        )
    return Store.objects.none()


def _get_selected_store(request, user_stores):
    """The store to act on: from ?store_id=, falling back to the first one."""
    selected_store_id = request.GET.get("store_id")
    if selected_store_id:
        return user_stores.filter(id=selected_store_id).first()
    return user_stores.first()


def _get_quota_info(offer, store):
    if not store:
        return None
    formatted_wilaya_code = str(store.wilaya).zfill(2)
    return OfferQuota.objects.filter(
        offer=offer, wilaya_code=formatted_wilaya_code
    ).first()


# ---------------------------------------------------------------------------
# POST input parsing / validation
# ---------------------------------------------------------------------------

def _parse_quantity(request):
    """Returns (quantity, error_message). quantity is None if invalid."""
    try:
        quantity = int(request.POST.get("quantity", 1))
        if quantity < 1:
            raise ValueError
        return quantity, None
    except ValueError:
        return None, "Please enter a valid quantity of at least 1."


def _validate_store_for_purchase(request, selected_store):
    """Returns an error message if the store can't be used to buy, else None."""
    if not request.user.is_authenticated or not selected_store:
        return "You must select a valid, accepted store to place an order."
    if selected_store.status != Store.STATUS_APPROVED:
        return "This store isn't approved yet — purchases aren't allowed."
    return None


# ---------------------------------------------------------------------------
# Intent handlers — each returns an HttpResponseRedirect
# ---------------------------------------------------------------------------

def _handle_draft_intent(request, offer, plan, selected_store, quantity):
    formatted_wilaya_code = str(selected_store.wilaya).zfill(2)

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

    store_room_left = current_quota.remaining_for_store(selected_store)
    if quantity > store_room_left:
        messages.error(
            request,
            f"Can't add {quantity} — your store can request at most "
            f"{current_quota.max_quantity_per_client} units "
            f"({current_quota.percentage_by_client}% of quota) for this offer. "
            f"{store_room_left} still available to you.",
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


def _handle_waitlist_intent(request, offer, plan, selected_store, quantity):
    with transaction.atomic():
        existing_waitlist = StoreOfferTransaction.objects.filter(
            store=selected_store,
            plan=plan,
            status=StoreOfferTransaction.STATUS_WAITLISTED,
        ).first()
        if existing_waitlist:
            existing_waitlist.quantity_bought += quantity
            existing_waitlist.save(update_fields=["quantity_bought"])
        else:
            StoreOfferTransaction.objects.create(
                store=selected_store,
                plan=plan,
                quantity_bought=quantity,
                status=StoreOfferTransaction.STATUS_WAITLISTED,
            )

    messages.success(
        request,
        f"You're queued for {quantity}x '{plan.label}' — "
        f"{selected_store.name} will get it automatically once quota is replenished.",
    )
    return redirect("offer_detail_page", offer_slug=offer.slug)


def _handle_buy_now_intent(request, offer, plan, selected_store, quantity):
    formatted_wilaya_code = str(selected_store.wilaya).zfill(2)

    with transaction.atomic():
        current_quota = (
            OfferQuota.objects.select_for_update()
            .filter(offer=offer, wilaya_code=formatted_wilaya_code)
            .first()
        )

        store_room_left = (
            current_quota.remaining_for_store(selected_store) if current_quota else 0
        )

        can_fulfill = (
            current_quota
            and current_quota.is_available(quantity)
            and quantity <= store_room_left
        )

        if can_fulfill:
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

        # Failure paths
        if current_quota and current_quota.is_available(quantity) and quantity > store_room_left:
            messages.error(
                request,
                f"Order failed. Your store can request at most "
                f"{current_quota.max_quantity_per_client} units "
                f"({current_quota.percentage_by_client}% of quota) for this offer. "
                f"{store_room_left} still available to you. "
                f"You can join the waitlist instead.",
            )
        else:
            available = current_quota.remaining_quota if current_quota else 0
            messages.error(
                request,
                f"Order failed. Requested {quantity} units, but only {available} remaining for your Wilaya. "
                f"You can join the waitlist instead.",
            )

    return redirect("offer_detail_page", offer_slug=offer.slug)


def _handle_purchase_post(request, offer, selected_store):
    """Dispatches a POST to the right intent handler."""
    store_error = _validate_store_for_purchase(request, selected_store)
    if store_error:
        messages.error(request, store_error)
        return redirect("offer_detail_page", offer_slug=offer.slug)

    plan_id = request.POST.get("plan_id")
    plan = get_object_or_404(OfferPlan, id=plan_id, offer=offer)
    intent = request.POST.get("intent")  # "draft", "buy_now" or "waitlist"

    quantity, quantity_error = _parse_quantity(request)
    if quantity_error:
        messages.error(request, quantity_error)
        return redirect("offer_detail_page", offer_slug=offer.slug)

    if intent == "draft":
        return _handle_draft_intent(request, offer, plan, selected_store, quantity)
    elif intent == "waitlist":
        return _handle_waitlist_intent(request, offer, plan, selected_store, quantity)
    else:
        return _handle_buy_now_intent(request, offer, plan, selected_store, quantity)


# ---------------------------------------------------------------------------
# Context building
# ---------------------------------------------------------------------------

def _get_store_waitlist_total(offer, selected_store):
    if not selected_store:
        return None
    return (
        StoreOfferTransaction.objects.filter(
            store=selected_store,
            plan__offer=offer,
            status=StoreOfferTransaction.STATUS_WAITLISTED,
        ).aggregate(total=Sum("quantity_bought"))["total"]
        or 0
    )


def _build_context(offer, offer_plans, user_stores, selected_store, quota_info):
    return {
        "offer": offer,
        "offer_plans": offer_plans,
        "user_stores": user_stores,
        "selected_store": selected_store,
        "quota_info": quota_info,
        "store_purchase_room": (
            quota_info.remaining_for_store(selected_store)
            if quota_info and selected_store
            else None
        ),
        "store_waitlist_total": _get_store_waitlist_total(offer, selected_store),
    }


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

def offer_detail_page(request, offer_slug):
    offer = get_object_or_404(Offer, slug=offer_slug, is_active=True)
    offer_plans = offer.plans.all()

    user_stores = _get_user_stores(request)
    selected_store = _get_selected_store(request, user_stores)
    quota_info = _get_quota_info(offer, selected_store)

    if request.method == "POST":
        return _handle_purchase_post(request, offer, selected_store)

    context = _build_context(offer, offer_plans, user_stores, selected_store, quota_info)
    return render(request, "core/offer_details_page.html", context)