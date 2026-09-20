from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import F
from django.db import transaction
from django.contrib import messages
from django.urls import reverse

from core.models import OfferQuota
from ..forms import OfferSaleForm
from ..models import Store, StoreOfferTransaction, StoreStock, OfferSale

########## Pages ##########

@login_required(login_url="client_login")
def client_offer_manage_page(request):
    client = request.user.client_profile
    stores = Store.objects.filter(client=client, status=Store.STATUS_APPROVED).order_by(
        "name"
    )

    if not stores.exists():
        messages.info(request, "You don't have any store yet. Add one first.")
        return render(
            request,
            "clients/client_manage_offer_page.html",
            {
                "store": None,
                "stores": stores,
                "stock_list": [],
                "sales": [],
                "form": None,
            },
        )

    store_id = request.GET.get("store") or request.POST.get("store_id_selected")
    store = None
    if store_id:
        store = stores.filter(id=store_id).first()
    if store is None:
        store = stores.first()

    if request.method == "POST":
        form = OfferSaleForm(request.POST, store=store)
        if form.is_valid():
            with transaction.atomic():
                stock = StoreStock.objects.select_for_update().get(
                    store=store, plan_id=form.cleaned_data["plan_id"]
                )

                if stock.remaining < 1:
                    form.add_error(None, "Stock changed — nothing left. Try again.")
                else:
                    stock.sold = F("sold") + 1
                    stock.save(update_fields=["sold"])

                    OfferSale.objects.create(
                        store=store,
                        plan_id=form.cleaned_data["plan_id"],
                        phone_number=form.cleaned_data["phone_number"],
                        sold_by=request.user,
                    )
                    messages.success(request, "Offer sold successfully.")
                    return redirect(
                        f"{reverse('client_offer_manage_page')}?store={store.id}"
                    )
    else:
        form = OfferSaleForm(store=store)

    stock_qs = (
        StoreStock.objects.filter(store=store)
        .select_related("plan__offer")
        .order_by("plan__offer__title", "plan__label")
    )
    sales_qs = (
        OfferSale.objects.filter(store=store)
        .select_related("plan__offer")
        .order_by("-created_at")[:50]
    )

    return render(
        request,
        "clients/client_manage_offer_page.html",
        {
            "store": store,
            "stores": stores,
            "stock_list": stock_qs,
            "sales": sales_qs,
            "form": form,
        },
    )

@login_required(login_url="client_login")
def client_offer_draft_and_stock_page(request):
    client = request.user.client_profile
    stores = Store.objects.filter(client=client, status=Store.STATUS_APPROVED).order_by("name")

    if not stores.exists():
        messages.info(request, "You don't have any store yet. Add one first.")
        return render(
            request,
            "clients/client_offer_draft_and_stock_page.html",
            {
                "store": None,
                "stores": stores,
                "draft_items": [],
                "pending_items": [],
                "accepted_items": [],
                "blocked_items": [],
                "stock_list": [],
            },
        )

    store_id = request.GET.get("store") or request.POST.get("store_id")
    store = None
    if store_id:
        store = stores.filter(id=store_id).first()
    if store is None:
        store = stores.first()

    if request.method == "POST" and request.POST.get("action") == "submit_draft":
        tx = get_object_or_404(
            StoreOfferTransaction,
            id=request.POST.get("tx_id"),
            store=store,
            status=StoreOfferTransaction.STATUS_DRAFT,
        )
        formatted_wilaya_code = str(store.wilaya).zfill(2)

        with transaction.atomic():
            quota = (OfferQuota.objects.select_for_update().filter(offer=tx.plan.offer, wilaya_code=formatted_wilaya_code).first())
            if quota and quota.is_available(tx.quantity_bought):
                quota.allocated_quota += tx.quantity_bought
                quota.save()
                tx.status = StoreOfferTransaction.STATUS_PENDING
                tx.save()
                messages.success(request, f"'{tx.plan.label}' moved to pending.")
            else:
                available = quota.remaining_quota if quota else 0
                messages.error(
                    request,
                    f"Not enough quota left ({available} available) — couldn't submit '{tx.plan.label}'.",
                )
        return redirect(f"{reverse('client_offer_draft_and_stock_page')}?store={store.id}")

    transactions_qs = StoreOfferTransaction.objects.filter(store=store).select_related("plan__offer")

    draft_items = transactions_qs.filter(status=StoreOfferTransaction.STATUS_DRAFT).order_by("-created_at")
    pending_items = transactions_qs.filter(status=StoreOfferTransaction.STATUS_PENDING).order_by("-created_at")
    accepted_items = transactions_qs.filter(status=StoreOfferTransaction.STATUS_APPROVED).order_by("-created_at")
    blocked_items = transactions_qs.filter(status=StoreOfferTransaction.STATUS_BLOCKED).order_by("-created_at")

    stock_qs = ( StoreStock.objects.filter(store=store).select_related("plan__offer").order_by("plan__offer__title", "plan__label"))

    return render(
        request,
        "clients/client_offer_draft_and_stock_page.html",
        {
            "store": store,
            "stores": stores,
            "draft_items": draft_items,
            "pending_items": pending_items,
            "accepted_items": accepted_items,
            "blocked_items": blocked_items,
            "stock_list": stock_qs,
        },
    )
