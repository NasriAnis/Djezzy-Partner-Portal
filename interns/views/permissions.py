from django.contrib import messages
from django.shortcuts import get_object_or_404

MANAGE_OFFERS = "MO"
MANAGE_CLIENTS = "MC"
MANAGE_ALL = "MA"

def can_access(commercial_rights, *allowed_types):
    """True if commercial_rights has MANAGE_ALL or any of allowed_types."""
    return MANAGE_ALL in commercial_rights or bool(commercial_rights & set(allowed_types))


def can_perform(can_edit, commercial_type, *allowed_types):
    """Full write-permission check: edit rights + valid role."""
    return can_edit and can_access(commercial_type, *allowed_types)


def guard(
    request,
    can_edit,
    commercial_type,
    *allowed_types,
    redirect_to,
    message="You don't have access to do this."
):
    """Inline permission guard for views with varying redirect targets."""
    if can_perform(can_edit, commercial_type, *allowed_types):
        return None
    messages.error(request, message)
    return redirect_to


def scope_by_commercial(queryset, commercial, commercial_rights, field="commmercial"):
    if MANAGE_ALL in commercial_rights:
        return queryset
    return queryset.filter(**{field: commercial})


def get_scoped_or_404(model_qs, commercial, commercial_type, *, field="commmercial", **lookup):
    """get_object_or_404, restricted to the commercial's own scope."""
    return get_object_or_404(
        scope_by_commercial(model_qs, commercial, commercial_type, field=field),
        **lookup,
    )