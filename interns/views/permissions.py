from django.contrib import messages

# Access-right codes — mirrors Commercial.access_rights choices
MANAGE_OFFERS = "MO"
MANAGE_CLIENTS = "MC"
MANAGE_ALL = "MA"


def can_access(commercial_type, *allowed_types):
    """True if commercial_type is in allowed_types or is MANAGE_ALL."""
    return commercial_type == MANAGE_ALL or commercial_type in allowed_types


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


def scope_by_commercial(queryset, commercial, commercial_type, field="commmercial"):
    """Restricts queryset to commercial unless commercial_type is MANAGE_ALL."""
    if commercial_type == MANAGE_ALL:
        return queryset
    return queryset.filter(**{field: commercial})
