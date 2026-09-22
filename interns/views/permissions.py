from django.contrib import messages

# Access-right codes — mirrors Commercial.access_rights choices
MANAGE_OFFERS = "MO"
MANAGE_CLIENTS = "MC"
MANAGE_ALL = "MA"


def can_access(commercial_type, *allowed_types):
    """
    True if commercial_type is one of allowed_types, or is MANAGE_ALL.
    MA always passes here — this is the single place that fact lives,
    so adding new roles later never requires touching MA's behavior.
    """
    return commercial_type == MANAGE_ALL or commercial_type in allowed_types


def can_perform(can_edit, commercial_type, *allowed_types):
    """
    Full write-permission check: must have edit rights on their account
    AND be one of allowed_types (or MA, which bypasses the type check).
    """
    return can_edit and can_access(commercial_type, *allowed_types)


def guard(request, can_edit, commercial_type, *allowed_types,
          redirect_to, message="You don't have access to do this."):
    """
    Inline permission guard for views with varying redirect targets.
    Returns an HttpResponseRedirect to send back if access is denied,
    or None if the caller should proceed.

    Usage:
        commercial, can_edit, commercial_type = get_commercial_info(request)
        denial = guard(
            request, can_edit, commercial_type, MANAGE_CLIENTS,
            redirect_to=redirect("commercials_store_detail_page", store_id=store_id),
        )
        if denial:
            return denial
    """
    if can_perform(can_edit, commercial_type, *allowed_types):
        return None
    messages.error(request, message)
    return redirect_to


def scope_by_commercial(queryset, commercial, commercial_type, field="commmercial"):
    """
    Restricts a queryset to rows belonging to `commercial`, unless
    commercial_type is MANAGE_ALL, in which case the queryset is
    returned unfiltered — MA sees every store/client/transaction in
    the system, not just their own.

    `field` is the ORM lookup path to the Commercial FK relative to
    the queryset's model — e.g. "commmercial" for Store, or
    "store__commmercial" for StoreOfferTransaction, or
    "locations__commmercial" for Client.

    Usage:
        my_stores = scope_by_commercial(Store.objects.all(), commercial, commercial_type)

        store = get_object_or_404(
            scope_by_commercial(Store.objects.select_related("client__user"),
                                 commercial, commercial_type),
            id=store_id,
        )
    """
    if commercial_type == MANAGE_ALL:
        return queryset
    return queryset.filter(**{field: commercial})
