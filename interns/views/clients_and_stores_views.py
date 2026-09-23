import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import DecimalField, ExpressionWrapper, F, Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db import transaction
from django.utils import timezone

from clients.models import Client, OfferSale, Store, StoreOfferTransaction, StoreStock
from notifications.utils import notify

from .utils_views import commercial_required, get_commercial_info
from .permissions import guard, scope_by_commercial, MANAGE_ALL, MANAGE_CLIENTS
from core.models import OfferQuota


@login_required(login_url="commercials_login")
@commercial_required
def commercials_clients_page(request):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    view_filter = request.GET.get("view", "all")
    context = {"view_filter": view_filter}

    if view_filter in ("pending_offers", "waitlist"):
        status = (
            StoreOfferTransaction.STATUS_PENDING
            if view_filter == "pending_offers"
            else StoreOfferTransaction.STATUS_WAITLISTED
        )
        order = "-created_at" if view_filter == "pending_offers" else "created_at"
        key = (
            "pending_transactions"
            if view_filter == "pending_offers"
            else "waitlisted_transactions"
        )

        context[key] = (
            scope_by_commercial(
                StoreOfferTransaction.objects.filter(status=status),
                commercial,
                commercial_type,
                field="store__commmercial",
            )
            .select_related("store__client__user", "plan__offer")
            .order_by(order)
        )
    else:
        clients = (
            scope_by_commercial(
                Client.objects.all(),
                commercial,
                commercial_type,
                field="locations__commmercial",
            )
            .select_related("user")
            .prefetch_related("locations")
        )

        location_filter = Q()
        pending_filter = Q(locations__status=Store.STATUS_PENDING)
        if commercial_type != MANAGE_ALL:
            location_filter &= Q(locations__commmercial=commercial)
            pending_filter &= Q(locations__commmercial=commercial)

        clients = clients.annotate(
            my_locations_count=Count(
                "locations", filter=location_filter, distinct=True
            ),
            inactive_locations_count=Count(
                "locations", filter=pending_filter, distinct=True
            ),
        )

        if view_filter == "pending":
            clients = clients.filter(inactive_locations_count__gt=0)

        context["clients"] = clients.distinct().order_by("user__date_joined")

    return render(request, "interns/commercials_clients_page.html", context)


@login_required(login_url="commercials_login")
@commercial_required
def commercials_store_detail_page(request, store_id):
    commercial, _, commercial_type = get_commercial_info(request)
    store = get_object_or_404(
        scope_by_commercial(
            Store.objects.select_related("client__user", "comune"),
            commercial,
            commercial_type,
        ),
        id=store_id,
    )
    return render(
        request, "interns/commercials_store_detail_page.html", {"store": store}
    )


@login_required(login_url="commercials_login")
@commercial_required
def commercials_client_detail_page(request, client_id):
    commercial, _, commercial_type = get_commercial_info(request)
    client = get_object_or_404(Client, id=client_id)
    stores = scope_by_commercial(client.locations.all(), commercial, commercial_type)

    transactions = (
        StoreOfferTransaction.objects.filter(store__in=stores)
        .select_related("store", "plan__offer")
        .order_by("-created_at")
    )

    line_total = ExpressionWrapper(
        F("quantity_bought") * F("plan__price_da"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )
    six_months_ago = timezone.now() - timedelta(days=180)

    monthly_qs = (
        StoreOfferTransaction.objects.filter(
            store__in=stores,
            status=StoreOfferTransaction.STATUS_APPROVED,
            created_at__gte=six_months_ago,
        )
        .annotate(month=TruncMonth("created_at"), line_total=line_total)
        .values("month")
        .annotate(offers_bought=Sum("quantity_bought"), spent=Sum("line_total"))
        .order_by("month")
    )

    stock = (
        StoreStock.objects.filter(store__in=stores)
        .select_related("store", "plan__offer")
        .order_by("store__name", "plan__offer__title")
    )
    selling_history = (
        OfferSale.objects.filter(store__in=stores)
        .select_related("store", "plan", "plan__offer")
        .order_by("created_at")
    )

    return render(
        request,
        "interns/commercials_client_detail_page.html",
        {
            "client": client,
            "stores": stores,
            "transactions": transactions,
            "stock": stock,
            "selling_history": selling_history,
            "monthly_labels_json": json.dumps(
                [row["month"].strftime("%b %Y") for row in monthly_qs]
            ),
            "monthly_bought_json": json.dumps(
                [row["offers_bought"] or 0 for row in monthly_qs]
            ),
            "monthly_spent_json": json.dumps(
                [float(row["spent"] or 0) for row in monthly_qs]
            ),
        },
    )


########### APIs ###########


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_approve_transaction(request, transaction_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    denial = guard(
        request,
        can_edit,
        commercial_type,
        MANAGE_CLIENTS,
        redirect_to=redirect("commercials_clients_page"),
    )
    if denial:
        return denial

    with transaction.atomic():
        trans = get_object_or_404(
            scope_by_commercial(
                StoreOfferTransaction.objects.select_for_update(),
                commercial,
                commercial_type,
                field="store__commmercial",
            ),
            id=transaction_id,
        )

        if trans.status != StoreOfferTransaction.STATUS_APPROVED:
            trans.status = StoreOfferTransaction.STATUS_APPROVED
            trans.save(update_fields=["status"])

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
    denial = guard(
        request,
        can_edit,
        commercial_type,
        MANAGE_CLIENTS,
        redirect_to=redirect("commercials_clients_page"),
    )
    if denial:
        return denial

    fallback_url = request.META.get("HTTP_REFERER") or reverse(
        "commercials_clients_page"
    )
    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "You must provide a reason.")
        return redirect(fallback_url)

    with transaction.atomic():
        trans = get_object_or_404(
            scope_by_commercial(
                StoreOfferTransaction.objects.select_for_update(),
                commercial,
                commercial_type,
                field="store__commmercial",
            ),
            id=transaction_id,
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
    denial = guard(
        request,
        can_edit,
        commercial_type,
        MANAGE_CLIENTS,
        redirect_to=redirect("commercials_store_detail_page", store_id=store_id),
    )
    if denial:
        return denial

    store = get_object_or_404(
        scope_by_commercial(Store.objects.all(), commercial, commercial_type),
        id=store_id,
    )

    if store.status != Store.STATUS_APPROVED:
        store.status = Store.STATUS_APPROVED
        store.save(update_fields=["status"])
        messages.success(request, f'"{store.name}" approved.')
        notify(store.client, f"Your store {store.name} has been approved!", store)

    return redirect(
        request.META.get("HTTP_REFERER", reverse("commercials_clients_page"))
    )


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_block_store(request, store_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    denial = guard(
        request,
        can_edit,
        commercial_type,
        MANAGE_CLIENTS,
        redirect_to=redirect("commercials_store_detail_page", store_id=store_id),
    )
    if denial:
        return denial

    store = get_object_or_404(
        scope_by_commercial(Store.objects.all(), commercial, commercial_type),
        id=store_id,
    )
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

    return redirect(fallback_url)


@login_required(login_url="commercials_login")
@commercial_required
@require_POST
def commercials_fulfill_waitlist_transaction(request, transaction_id):
    commercial, can_edit, commercial_type = get_commercial_info(request)
    denial = guard(
        request,
        can_edit,
        commercial_type,
        MANAGE_CLIENTS,
        redirect_to=redirect("commercials_clients_page"),
    )
    if denial:
        return denial

    fallback_url = request.META.get("HTTP_REFERER") or reverse(
        "commercials_clients_page"
    )

    with transaction.atomic():
        tx = get_object_or_404(
            scope_by_commercial(
                StoreOfferTransaction.objects.select_for_update().filter(
                    status=StoreOfferTransaction.STATUS_WAITLISTED,
                ),
                commercial,
                commercial_type,
                field="store__commmercial",
            ),
            id=transaction_id,
        )

        formatted_wilaya_code = str(tx.store.wilaya).zfill(2)
        quota = (
            OfferQuota.objects.select_for_update()
            .filter(offer=tx.plan.offer, wilaya_code=formatted_wilaya_code)
            .first()
        )

        pool_available = quota.remaining_quota if quota else 0
        store_available = quota.remaining_for_store(tx.store) if quota else 0

        if pool_available <= 0:
            messages.error(
                request,
                f"No quota left for {tx.store.name}'s wilaya — {tx.quantity_bought} units still waiting.",
            )
            return redirect(fallback_url)

        if store_available <= 0:
            messages.error(
                request,
                f"{tx.store.name} is already at its per-store cap ({quota.max_quantity_per_client} units) for this offer — {tx.quantity_bought} units still waiting.",
            )
            return redirect(fallback_url)

        approved_qty = min(tx.quantity_bought, pool_available, store_available)

        stock_obj, created = StoreStock.objects.select_for_update().get_or_create(
            store=tx.store, plan=tx.plan, defaults={"stock": approved_qty}
        )
        if not created:
            stock_obj.stock = F("stock") + approved_qty
            stock_obj.save(update_fields=["stock"])

        quota.allocated_quota += approved_qty
        quota.save(update_fields=["allocated_quota"])

        if tx.quantity_bought <= approved_qty:
            tx.status = StoreOfferTransaction.STATUS_APPROVED
            tx.save(update_fields=["status"])
            messages.success(
                request,
                f"Approved {approved_qty}x '{tx.plan.label}' for {tx.store.name}.",
            )
            notify(
                tx.store.client,
                f"Your transaction for {approved_qty}x '{tx.plan.label}' has been approved!",
                tx.store,
            )
        else:
            StoreOfferTransaction.objects.create(
                store=tx.store,
                plan=tx.plan,
                quantity_bought=approved_qty,
                status=StoreOfferTransaction.STATUS_APPROVED,
            )
            tx.quantity_bought -= approved_qty
            tx.save(update_fields=["quantity_bought"])

            messages.success(
                request,
                f"Approved {approved_qty}x '{tx.plan.label}' for {tx.store.name} ({tx.quantity_bought} units still waiting).",
            )
            notify(
                tx.store.client,
                f"{approved_qty}x '{tx.plan.label}' from your waitlisted request has been approved! ({tx.quantity_bought} still waiting)",
                tx.store,
            )

    return redirect(fallback_url)
