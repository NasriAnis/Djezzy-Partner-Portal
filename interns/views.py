from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Count, Q
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse
from django.db import transaction

from core.models import Offer, OfferPlan, OfferQuota, WILAYA_CHOICES
from clients.models import Client, Store, StoreOfferTransaction, StoreStock
from interns.forms import OfferCategoryForm, OfferForm, OfferPlanForm, OfferQuotaForm, OfferCategory
from notifications.utils import notify

########### Utils ###########

def _get_commercial(request):
    """Helper: returns (commercial, can_edit)."""
    commercial = getattr(request.user, 'commercial_profile', None)
    can_edit = bool(commercial) and commercial.access_rights == commercial.AccessRights.READ_WRITE
    return commercial, can_edit

def commercials_logout(request):
    logout(request)
    return redirect('commercials_login')

########### Pages ###########

def commercials_index_page(request):
    if request.user.is_authenticated:
        return redirect('commercials_dashboard_page')
    return redirect('commercials_login')


def commercials_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('commercials_dashboard_page')
        else:
            return render(request, 'interns/commercials_login_page.html', {'error': 'Invalid credentials'})
    return render(request, 'interns/commercials_login_page.html')


@login_required(login_url='commercials_login')
def commercials_dashboard_page(request):
    revenue_expr = ExpressionWrapper(
        F('quantity_bought') * F('plan__price_da'),
        output_field=DecimalField(max_digits=14, decimal_places=2)
    )

    context = {
        'offers_count': Offer.objects.count(),
        'clients_count': Client.objects.count(),
        'stores_count': Store.objects.count(),
        'recent_stores': Store.objects.select_related('client__user').order_by('-created_at')[:5],
    }
    return render(request, 'interns/commercials_dashboard_page.html', context)


@login_required(login_url='commercials_login')
def commercials_offers_page(request):
    _, can_edit = _get_commercial(request)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, "You have read-only access.")
            return redirect('commercials_offers_page')

        form_type = request.POST.get('form_type')

        if form_type == 'add_category':
            cat_form = OfferCategoryForm(request.POST)
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Category created.")
            else:
                messages.error(request, "Could not create category — check the form.")
            return redirect('commercials_offers_page')

        elif form_type == 'edit_category':
            category = get_object_or_404(OfferCategory, id=request.POST.get('category_id'))
            cat_form = OfferCategoryForm(request.POST, instance=category)
            if cat_form.is_valid():
                cat_form.save()
                messages.success(request, "Category updated.")
            else:
                messages.error(request, "Could not update category — check the form.")
            return redirect('commercials_offers_page')

        elif form_type == 'delete_category':
            category = get_object_or_404(OfferCategory, id=request.POST.get('category_id'))
            if category.offers.exists():
                messages.error(request, f"Can't delete '{category.name}' — it still has offers assigned to it.")
            else:
                category_name = category.name
                category.delete()
                messages.success(request, f"Category '{category_name}' deleted.")
            return redirect('commercials_offers_page')

        elif form_type == 'add_offer':
            offer_form = OfferForm(request.POST, request.FILES)
            if offer_form.is_valid():
                offer_form.save()
                messages.success(request, "Offer created.")
            else:
                messages.error(request, "Could not create offer — check the form.")
            return redirect('commercials_offers_page')

    offers = Offer.objects.select_related('category').prefetch_related('plans').all()
    categories = OfferCategory.objects.all().order_by('order')
    return render(request, 'interns/commercials_offers_page.html', {
        'offers': offers,
        'categories': categories,
        'can_edit': can_edit,
        'category_form': OfferCategoryForm(),
        'offer_form': OfferForm(),
    })


@login_required(login_url='commercials_login')
def commercials_offer_edit_page(request, slug):
    offer = get_object_or_404(Offer, slug=slug)
    _, can_edit = _get_commercial(request)

    if request.method == 'POST':
        if not can_edit:
            messages.error(request, "You have read-only access.")
            return redirect('commercials_offer_edit_page', slug=slug)

        form_type = request.POST.get('form_type')

        if form_type == 'update_offer':
            offer.title = request.POST.get('title')
            offer.description = request.POST.get('description')
            offer.is_active = request.POST.get('is_active') == 'on'
            offer.is_new = request.POST.get('is_new') == 'on'
            if request.FILES.get('image'):
                offer.image = request.FILES['image']
            offer.save()
            messages.success(request, "Offer updated.")

        elif form_type == 'delete_offer':
            offer_title = offer.title
            offer.delete()
            messages.success(request, f"Offer '{offer_title}' deleted.")
            return redirect('commercials_offers_page')

        elif form_type == 'add_plan':
            plan_form = OfferPlanForm(request.POST)
            if plan_form.is_valid():
                plan = plan_form.save(commit=False)
                plan.offer = offer
                plan.save()
                messages.success(request, "Plan added.")
            else:
                messages.error(request, "Could not add plan — check the form.")

        elif form_type == 'edit_plan':
            plan = get_object_or_404(OfferPlan, id=request.POST.get('plan_id'), offer=offer)
            plan_form = OfferPlanForm(request.POST, instance=plan)
            if plan_form.is_valid():
                plan_form.save()
                messages.success(request, "Plan updated.")
            else:
                messages.error(request, "Could not update plan — check the form.")

        elif form_type == 'delete_plan':
            plan = get_object_or_404(OfferPlan, id=request.POST.get('plan_id'), offer=offer)
            plan.delete()
            messages.success(request, "Plan deleted.")

        elif form_type == 'add_quota':
            quota_form = OfferQuotaForm(request.POST)
            if quota_form.is_valid():
                quota = quota_form.save(commit=False)
                quota.offer = offer
                try:
                    quota.save()
                    messages.success(request, "Quota added.")
                except Exception:
                    messages.error(request, "A quota for this wilaya already exists.")
            else:
                messages.error(request, "Could not add quota — check the form.")

        elif form_type == 'edit_quota':
            quota = get_object_or_404(OfferQuota, id=request.POST.get('quota_id'), offer=offer)
            quota_form = OfferQuotaForm(request.POST, instance=quota)
            if quota_form.is_valid():
                quota_form.save()
                messages.success(request, "Quota updated.")
            else:
                messages.error(request, "Could not update quota — check the form.")

        elif form_type == 'delete_quota':
            quota = get_object_or_404(OfferQuota, id=request.POST.get('quota_id'), offer=offer)
            quota.delete()
            messages.success(request, "Quota deleted.")

        return redirect('commercials_offer_edit_page', slug=offer.slug)

    return render(request, 'interns/commercials_offer_edit_page.html', {
        'offer': offer,
        'plans': offer.plans.all(),
        'quotas': offer.wilaya_quotas.all(),
        'can_edit': can_edit,
        'plan_form': OfferPlanForm(),
        'quota_form': OfferQuotaForm(),
    })


@login_required(login_url='commercials_login')
def commercials_clients_page(request):
    view_filter = request.GET.get('view', 'all')
    context = {'view_filter': view_filter}

    if view_filter == 'pending_offers':
        pending_transactions = (
            StoreOfferTransaction.objects
            .filter(status=StoreOfferTransaction.STATUS_PENDING)
            .select_related('store__client__user', 'plan__offer')
            .order_by('-created_at')
        )
        context['pending_transactions'] = pending_transactions

    else:
        clients = (
            Client.objects
            .select_related('user')
            .prefetch_related('locations')
            .annotate(
                inactive_locations_count=Count(
                    'locations', filter=Q(locations__status=Store.STATUS_PENDING)
                )
            )
        )
        if view_filter == 'pending':
            clients = clients.filter(inactive_locations_count__gt=0)

        context['clients'] = clients.distinct().order_by('user__date_joined')

    return render(request, 'interns/commercials_clients_page.html', context)


@login_required(login_url='commercials_login')
def commercials_store_detail_page(request, store_id):
    store = get_object_or_404(
        Store.objects.select_related('client__user', 'comune'),
        id=store_id
    )
    return render(request, 'interns/commercials_store_detail_page.html', {'store': store})




@login_required(login_url='commercials_login')
def commercials_client_detail_page(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    stores = client.locations.all()
    transactions = StoreOfferTransaction.objects.filter(store__in=stores) \
        .select_related('store', 'plan__offer').order_by('-created_at')

    return render(request, 'interns/commercials_client_detail_page.html', {
        'client': client,
        'stores': stores,
        'transactions': transactions,
    })


########### APIs ###########

@login_required(login_url='commercials_login')
@require_POST
def commercials_approve_transaction(request, transaction_id):
    commercial_profile, can_edit = _get_commercial(request)
    if not can_edit:
        messages.error(request, "You have read-only access.")
        return redirect('commercials_clients_page')

    with transaction.atomic():
        # Lock transaction row during approval
        trans = get_object_or_404(
            StoreOfferTransaction.objects.select_for_update(),
            id=transaction_id
        )

        if trans.status != StoreOfferTransaction.STATUS_APPROVED:
            trans.status = StoreOfferTransaction.STATUS_APPROVED
            trans.save(update_fields=['status'])

            # Ensure unique row per (store, plan) and atomically update stock
            stock_obj, created = StoreStock.objects.select_for_update().get_or_create(
                store=trans.store,
                plan=trans.plan,
                defaults={'stock': trans.quantity_bought}
            )

            if not created:
                stock_obj.stock = F('stock') + trans.quantity_bought
                stock_obj.save(update_fields=['stock'])

            messages.success(request, f"Offer for {trans.store.name} approved.")
            notify(
                trans.store.client,
                f"Your transaction {trans.quantity_bought} has been approved!",
                trans.store
            )

    return redirect(request.META.get('HTTP_REFERER', reverse('commercials_clients_page')))

@login_required(login_url='commercials_login')
@require_POST
def commercials_deny_transaction(request, transaction_id):
    commercial_profile, can_edit = _get_commercial(request)
    if not can_edit:
        messages.error(request, "You have read-only access.")
        return redirect('commercials_clients_page')

    fallback_url = request.META.get('HTTP_REFERER') or reverse('commercials_clients_page')

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "You must provide a reason.")
        return redirect(fallback_url)

    with transaction.atomic():
        # Lock transaction row during approval
        trans = get_object_or_404(
            StoreOfferTransaction.objects.select_for_update(),
            id=transaction_id
        )

        if trans.status != StoreOfferTransaction.STATUS_BLOCKED:
            trans.status = StoreOfferTransaction.STATUS_BLOCKED
            trans.comment = reason
            trans.save(update_fields=['status', 'comment'])

            messages.success(request, f"Offer for {trans.store.name} blocked.")
            notify(
                trans.store.client,
                f"Your transaction {trans.quantity_bought} has not been approved: {reason}",
                trans.store
            )
        else:
            messages.info(request, "This transaction was already blocked.")

    return redirect(fallback_url)

@login_required(login_url='commercials_login')
@require_POST
def commercials_approve_store(request, store_id):
    commercial_profile, can_edit = _get_commercial(request)
    if not can_edit:
        messages.error(request, "You have read-only access.")
        return redirect('commercials_store_detail_page', store_id=store_id)

    store = get_object_or_404(Store, id=store_id)

    if store.status != Store.STATUS_APPROVED:
        store.status = Store.STATUS_APPROVED
        store.save(update_fields=['status'])
        messages.success(request, f'"{store.name}" approved.')
        notify(store.client, f"Your store {store.name} has been approved!", store),

    return redirect(request.META.get('HTTP_REFERER', reverse('commercials_clients_page')))

@login_required(login_url='commercials_login')
@require_POST
def commercials_block_store(request, store_id):
    _, can_edit = _get_commercial(request)
    if not can_edit:
        messages.error(request, "You have read-only access.")
        return redirect('commercials_store_detail_page', store_id=store_id)

    store = get_object_or_404(Store, id=store_id)
    fallback_url = request.META.get('HTTP_REFERER') or reverse('commercials_clients_page')

    reason = request.POST.get("reason", "").strip()
    if not reason:
        messages.error(request, "You must provide a reason.")
        return redirect(fallback_url)

    if store.status != Store.STATUS_BLOCKED:
        store.status = Store.STATUS_BLOCKED
        store.save(update_fields=['status'])
        messages.success(request, f'"{store.name}" blocked.')
        notify(store.client, f"Your store {store.name} has been blocked: {reason}", store)

    return redirect(fallback_url)