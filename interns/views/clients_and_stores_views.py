from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import F, Count, Q
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db import transaction

from clients.models import Client, Store, StoreOfferTransaction, StoreStock
from notifications.utils import notify

from .utils_views import commercial_required, get_commercial_info
from core.models import OfferQuota


@login_required(login_url="commercials_login")
@commercial_required
def commercials_clients_page(request):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    view_filter = request.GET.get("view", "all")
    context = {"view_filter": view_filter}

    if view_filter == "pending_offers":
        pending_transactions = (
            StoreOfferTransaction.objects.filter(
                status=StoreOfferTransaction.STATUS_PENDING,
                store__commmercial=commercial,
            )
            .select_related("store__client__user", "plan__offer")
            .order_by("-created_at")
        )
        context["pending_transactions"] = pending_transactions

    elif view_filter == "waitlist":
        waitlisted_transactions = (
            StoreOfferTransaction.objects.filter(
                status=StoreOfferTransaction.STATUS_WAITLISTED,
                store__commmercial=commercial,
            )
            .select_related("store__client__user", "plan__offer")
            .order_by("created_at")  # oldest first matches FIFO fulfillment order
        )
        context["waitlisted_transactions"] = waitlisted_transactions

    else:
        clients = (
            Client.objects.filter(locations__commmercial=commercial)
            .select_related("user")
            .prefetch_related("locations")
            .annotate(
                my_locations_count=Count(
                    "locations",
                    filter=Q(locations__commmercial=commercial),
                    distinct=True,
                ),
                inactive_locations_count=Count(
                    "locations",
                    filter=Q(
                        locations__status=Store.STATUS_PENDING,
                        locations__commmercial=commercial,
                    ),
                    distinct=True,
                ),
            )
        )
        if view_filter == "pending":
            clients = clients.filter(inactive_locations_count__gt=0)

        context["clients"] = clients.distinct().order_by("user__date_joined")

    return render(request, "interns/commercials_clients_page.html", context)


@login_required(login_url="commercials_login")
@commercial_required
def commercials_store_detail_page(request, store_id):
    commercial, _, _ = get_commercial_info(request)
    store = get_object_or_404(
        Store.objects.select_related("client__user", "comune"),
        id=store_id,
        commmercial=commercial,
    )
    return render(
        request, "interns/commercials_store_detail_page.html", {"store": store}
    )


@login_required(login_url="commercials_login")
@commercial_required
def commercials_client_detail_page(request, client_id):
    commercial, _, _ = get_commercial_info(request)
    client = get_object_or_404(Client, id=client_id)
    stores = client.locations.filter(commmercial=commercial)
    transactions = (
        StoreOfferTransaction.objects.filter(store__in=stores)
        .select_related("store", "plan__offer")
        .order_by("-created_at")
    )

    return render(
        request,
        "interns/commercials_client_detail_page.html",
        {
            "client": client,
            "stores": stores,
            "transactions": transactions,
        },
    )


########### APIs ###########


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_approve_transaction(request, transaction_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not can_edit and commercial_type != "MC":
        messages.error(request, "You have read-only access.")
        return redirect("commercials_clients_page")

    with transaction.atomic():
        # Lock transaction row during approval
        trans = get_object_or_404(
            StoreOfferTransaction.objects.select_for_update(),
            id=transaction_id,
            store__commmercial=commercial,
        )

        if trans.status != StoreOfferTransaction.STATUS_APPROVED:
            trans.status = StoreOfferTransaction.STATUS_APPROVED
            trans.save(update_fields=["status"])

            # Ensure unique row per (store, plan) and atomically update stock
            stock_obj, created = StoreStock.objects.select_for_update().get_or_create(
                store=trans.store,
                plan=trans.plan,
                defaults={"stock": trans.quantity_bought},
            )

            if not created:
                stock_obj.stock = F("stock") + trans.quantity_bought
                stock_obj.save(update_fields=["stock"])

            messages.success(request, f"Offer for {trans.store.name} approved.")
            notify(
                trans.store.client,
                f"Your transaction {trans.quantity_bought} has been approved!",
                trans.store,
            )

    return redirect(
        request.META.get("HTTP_REFERER", reverse("commercials_clients_page"))
    )


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_deny_transaction(request, transaction_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not can_edit and commercial_type != "MC":
        messages.error(request, "You have read-only access.")
        return redirect("commercials_clients_page")

    fallback_url = request.META.get("HTTP_REFERER") or reverse(
        "commercials_clients_page"
    )

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "You must provide a reason.")
        return redirect(fallback_url)

    with transaction.atomic():
        # Lock transaction row during approval
        trans = get_object_or_404(
            StoreOfferTransaction.objects.select_for_update(),
            id=transaction_id,
            store__commmercial=commercial,
        )

        if trans.status != StoreOfferTransaction.STATUS_BLOCKED:
            trans.status = StoreOfferTransaction.STATUS_BLOCKED
            trans.comment = reason
            trans.save(update_fields=["status", "comment"])

            messages.success(request, f"Offer for {trans.store.name} blocked.")
            notify(
                trans.store.client,
                f"Your transaction {trans.quantity_bought} has not been approved: {reason}",
                trans.store,
            )
        else:
            messages.info(request, "This transaction was already blocked.")

    return redirect(fallback_url)


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_approve_store(request, store_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not can_edit and commercial_type != "MC":
        messages.error(request, "You have read-only access.")
        return redirect("commercials_store_detail_page", store_id=store_id)

    store = get_object_or_404(Store, id=store_id, commmercial=commercial)

    if store.status != Store.STATUS_APPROVED:
        store.status = Store.STATUS_APPROVED
        store.save(update_fields=["status"])
        messages.success(request, f'"{store.name}" approved.')
        notify(store.client, f"Your store {store.name} has been approved!", store),

    return redirect(
        request.META.get("HTTP_REFERER", reverse("commercials_clients_page"))
    )


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_block_store(request, store_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not can_edit and commercial_type != "MC":
        messages.error(request, "You have read-only access.")
        return redirect("commercials_store_detail_page", store_id=store_id)

    store = get_object_or_404(Store, id=store_id, commmercial=commercial)
    fallback_url = request.META.get("HTTP_REFERER") or reverse(
        "commercials_clients_page"
    )

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "You must provide a reason.")
        return redirect(fallback_url)

    if store.status != Store.STATUS_BLOCKED:
        store.status = Store.STATUS_BLOCKED
        store.save(update_fields=["status"])
        messages.success(request, f'"{store.name}" blocked.')
        notify(
            store.client, f"Your store {store.name} has been blocked: {reason}", store
        )


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_fulfill_waitlist_transaction(request, transaction_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not can_edit and commercial_type != "MC":
        messages.error(request, "You have read-only access.")
        return redirect("commercials_clients_page")

    fallback_url = request.META.get("HTTP_REFERER") or reverse(
        "commercials_clients_page"
    )

    with transaction.atomic():
        tx = get_object_or_404(
            StoreOfferTransaction.objects.select_for_update(),
            id=transaction_id,
            store__commmercial=commercial,
            status=StoreOfferTransaction.STATUS_WAITLISTED,
        )

        formatted_wilaya_code = str(tx.store.wilaya).zfill(2)
        quota = (
            OfferQuota.objects.select_for_update()
            .filter(offer=tx.plan.offer, wilaya_code=formatted_wilaya_code)
            .first()
        )

        available = quota.remaining_for_store(tx.store) if quota else 0

        if available <= 0:
            messages.error(
                request,
                f"No quota available yet for {tx.store.name} — "
                f"{tx.quantity_bought} units still waiting.",
            )
            return redirect(fallback_url)

        if tx.quantity_bought <= available:
            tx.status = StoreOfferTransaction.STATUS_PENDING
            tx.save(update_fields=["status"])
            quota.allocated_quota += tx.quantity_bought
            quota.save(update_fields=["allocated_quota"])

            messages.success(
                request,
                f"Moved {tx.quantity_bought}x '{tx.plan.label}' for {tx.store.name} "
                f"to Pending Offers — approve it there to finalize.",
            )
            notify(
                tx.store.client,
                f"Your waitlisted request for {tx.quantity_bought}x '{tx.plan.label}' "
                f"is now pending approval!",
                tx.store,
            )
        else:
            StoreOfferTransaction.objects.create(
                store=tx.store,
                plan=tx.plan,
                quantity_bought=available,
                status=StoreOfferTransaction.STATUS_PENDING,
            )
            tx.quantity_bought -= available
            tx.save(update_fields=["quantity_bought"])
            quota.allocated_quota += available
            quota.save(update_fields=["allocated_quota"])

            messages.success(
                request,
                f"Partially fulfilled {available}x '{tx.plan.label}' for {tx.store.name} "
                f"({tx.quantity_bought} units still waiting).",
            )
            notify(
                tx.store.client,
                f"{available}x '{tx.plan.label}' from your waitlisted request "
                f"is now pending approval! ({tx.quantity_bought} still waiting)",
                tx.store,
            )

    return redirect(fallback_url)
