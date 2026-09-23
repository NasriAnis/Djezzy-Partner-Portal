from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from core.models import Offer, OfferPlan, OfferQuota
from interns.forms import (
    OfferCategoryForm,
    OfferForm,
    OfferPlanForm,
    OfferQuotaForm,
    OfferCategory,
)
from shared.view_helpers import handle_form

from .utils_views import commercial_required, get_commercial_info
from .permissions import can_perform, MANAGE_OFFERS


@login_required(login_url="commercials_login")
@commercial_required
def commercials_offers_page(request):
    _, can_edit, commercial_type = get_commercial_info(request)

    if request.method == "POST":
        if not can_perform(can_edit, commercial_type, MANAGE_OFFERS):
            messages.error(request, "You don't have access to manage offers.")
            return redirect("commercials_offers_page")

        form_type = request.POST.get("form_type")

        if form_type == "add_category":
            handle_form(
                request,
                OfferCategoryForm,
                success="Category created.",
                error="Could not create category — check the form.",
            )

        elif form_type == "edit_category":
            category = get_object_or_404(
                OfferCategory, id=request.POST.get("category_id")
            )
            handle_form(
                request,
                OfferCategoryForm,
                instance=category,
                success="Category updated.",
                error="Could not update category — check the form.",
            )

        elif form_type == "delete_category":
            category = get_object_or_404(
                OfferCategory, id=request.POST.get("category_id")
            )
            if category.offers.exists():
                messages.error(
                    request,
                    f"Can't delete '{category.name}' — it still has offers assigned to it.",
                )
            else:
                messages.success(request, f"Category '{category.name}' deleted.")
                category.delete()

        elif form_type == "add_offer":
            handle_form(
                request,
                OfferForm,
                files=request.FILES,
                success="Offer created.",
                error="Could not create offer — check the form.",
            )

        return redirect("commercials_offers_page")

    offers = Offer.objects.select_related("category").prefetch_related("plans").all()
    categories = OfferCategory.objects.all().order_by("order")
    return render(
        request,
        "interns/commercials_offers_page.html",
        {
            "offers": offers,
            "categories": categories,
            "can_edit": can_edit,
            "category_form": OfferCategoryForm(),
            "offer_form": OfferForm(),
        },
    )


@login_required(login_url="commercials_login")
@commercial_required
def commercials_offer_edit_page(request, slug):
    offer = get_object_or_404(Offer, slug=slug)
    _, can_edit, commercial_type = get_commercial_info(request)

    if request.method == "POST":
        if not can_perform(can_edit, commercial_type, MANAGE_OFFERS):
            messages.error(request, "You don't have access to manage offers.")
            return redirect("commercials_offer_edit_page", slug=slug)

        form_type = request.POST.get("form_type")

        if form_type == "update_offer":
            offer.title = request.POST.get("title")
            offer.description = request.POST.get("description")
            offer.is_active = request.POST.get("is_active") == "on"
            offer.is_new = request.POST.get("is_new") == "on"
            if request.FILES.get("image"):
                offer.image = request.FILES["image"]
            offer.save()
            messages.success(request, "Offer updated.")

        elif form_type == "delete_offer":
            offer_title = offer.title
            offer.delete()
            messages.success(request, f"Offer '{offer_title}' deleted.")
            return redirect("commercials_offers_page")

        elif form_type == "add_plan":
            def _attach_offer(plan):
                plan.offer = offer
                plan.save()

            handle_form(
                request,
                OfferPlanForm,
                success="Plan added.",
                error="Could not add plan — check the form.",
                on_save=_attach_offer,
                commit=False,
            )

        elif form_type == "edit_plan":
            plan = get_object_or_404(
                OfferPlan, id=request.POST.get("plan_id"), offer=offer
            )
            handle_form(
                request,
                OfferPlanForm,
                instance=plan,
                success="Plan updated.",
                error="Could not update plan — check the form.",
            )

        elif form_type == "delete_plan":
            plan = get_object_or_404(
                OfferPlan, id=request.POST.get("plan_id"), offer=offer
            )
            plan.delete()
            messages.success(request, "Plan deleted.")

        elif form_type == "add_quota":
            def _attach_and_save_quota(quota):
                quota.offer = offer
                quota.save()

            handle_form(
                request,
                OfferQuotaForm,
                success="Quota added.",
                error="Could not add quota — check the form.",
                on_save=_attach_and_save_quota,
                commit=False,
                save_error="A quota for this wilaya already exists.",
            )

        elif form_type == "edit_quota":
            quota = get_object_or_404(
                OfferQuota, id=request.POST.get("quota_id"), offer=offer
            )

            def _save_and_process_waitlist(saved_quota):
                with transaction.atomic():
                    saved_quota.save()
                    saved_quota.refresh_from_db()
                    saved_quota.process_waitlist()

            handle_form(
                request,
                OfferQuotaForm,
                instance=quota,
                success="Quota updated.",
                error="Could not update quota — check the form.",
                on_save=_save_and_process_waitlist,
                commit=False,
            )

        elif form_type == "delete_quota":
            quota = get_object_or_404(
                OfferQuota, id=request.POST.get("quota_id"), offer=offer
            )
            quota.delete()
            messages.success(request, "Quota deleted.")

        return redirect("commercials_offer_edit_page", slug=offer.slug)

    return render(
        request,
        "interns/commercials_offer_edit_page.html",
        {
            "offer": offer,
            "plans": offer.plans.all(),
            "quotas": offer.wilaya_quotas.all(),
            "can_edit": can_edit,
            "plan_form": OfferPlanForm(),
            "quota_form": OfferQuotaForm(),
        },
    )