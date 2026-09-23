"""
Shared helpers for the interns (commercial) and clients view packages.
Keeping these in one place means a change to how we flash a message,
save a form, transition a status, or aggregate monthly stats only has
to happen here instead of in every view that does it.
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from notifications.utils import notify


########## Redirects / fallbacks ##########


def get_fallback_url(request, default_view_name, **kwargs):
    """The page the user came from, or a reversed URL if there's none."""
    return request.META.get("HTTP_REFERER") or reverse(default_view_name, kwargs=kwargs)


########## POST field helpers ##########


def require_post_field(request, field_name, fallback_url, error="This field is required."):
    """
    Reads and strips a POST field. Returns (value, None) if present,
    or (None, redirect_response) if missing/blank.

    Usage:
        reason, early_redirect = require_post_field(request, "reason", fallback_url)
        if early_redirect:
            return early_redirect
    """
    value = request.POST.get(field_name, "").strip()
    if not value:
        messages.error(request, error)
        return None, redirect(fallback_url)
    return value, None


########## Status transitions (approve / block / etc.) ##########


def transition_status(
    obj,
    *,
    new_status,
    status_field="status",
    extra_fields=None,
    request=None,
    success_msg=None,
    notify_target=None,
    notify_msg=None,
):
    """
    Moves obj.<status_field> to new_status if it isn't already there,
    saves it, and optionally flashes a message / sends a notification.

    Returns True if the transition happened, False if it was a no-op
    (already in that status) — callers use this to decide whether to
    run side effects like adjusting stock.
    """
    if getattr(obj, status_field) == new_status:
        return False

    setattr(obj, status_field, new_status)
    obj.save(update_fields=[status_field, *(extra_fields or [])])

    if request is not None and success_msg:
        messages.success(request, success_msg)

    if notify_target is not None and notify_msg:
        notify(notify_target, notify_msg, obj)

    return True


########## Form handling ##########


def handle_form(
    request,
    FormClass,
    *,
    instance=None,
    files=None,
    success="Saved.",
    error="Could not save — check the form.",
    on_save=None,
    commit=True,
    save_error=None,
):
    """
    Validates FormClass(request.POST, files, instance=instance) and
    flashes a message either way.

    - on_save(obj), if given, runs after form.save(commit=commit).
      Use it with commit=False when you need to set a field (like a
      FK) before the real save, or to wrap the save in extra logic.
    - If on_save raises and save_error is set, that message is shown
      instead of `success` and the exception is swallowed (used for
      "unique constraint" style failures). Without save_error, the
      exception propagates as usual.

    Returns the saved object, or None if the form was invalid or
    on_save failed with save_error set.
    """
    form = FormClass(request.POST, files or None, instance=instance)
    if not form.is_valid():
        messages.error(request, error)
        return None

    obj = form.save(commit=commit)

    if on_save:
        try:
            on_save(obj)
        except Exception:
            if save_error:
                messages.error(request, save_error)
                return None
            raise

    messages.success(request, success)
    return obj


########## Monthly revenue / quantity stats ##########


def line_total_expr(quantity_field="quantity_bought", price_field="plan__price_da"):
    return ExpressionWrapper(
        F(quantity_field) * F(price_field),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )


def monthly_stats(qs, *, since_days=180, qty_label="offers_sold", amount_label="revenue"):
    """
    Groups a transaction-like queryset by month over the last
    `since_days` days, summing quantity_bought and quantity*price.

    Returns (labels, quantities, amounts) — three parallel lists,
    ready to json.dumps straight into a template context.
    """
    cutoff = timezone.now() - timedelta(days=since_days)
    rows = (
        qs.filter(created_at__gte=cutoff)
        .annotate(month=TruncMonth("created_at"), _line_total=line_total_expr())
        .values("month")
        .annotate(**{qty_label: Sum("quantity_bought"), amount_label: Sum("_line_total")})
        .order_by("month")
    )
    labels = [row["month"].strftime("%b %Y") for row in rows]
    quantities = [row[qty_label] or 0 for row in rows]
    amounts = [float(row[amount_label] or 0) for row in rows]
    return labels, quantities, amounts


########## Email/password login ##########


def email_login_view(request, template_name, redirect_view, redirect_kwargs=None):
    """
    Shared body for the "email + password" login pages (commercials
    and clients). On success, redirects to redirect_view (a URL
    name), passing redirect_kwargs(user) as kwargs if it's callable,
    else redirect_kwargs itself.
    """
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            kwargs = redirect_kwargs(user) if callable(redirect_kwargs) else (redirect_kwargs or {})
            return redirect(redirect_view, **kwargs)
        return render(request, template_name, {"error": "Invalid credentials"})
    return render(request, template_name)