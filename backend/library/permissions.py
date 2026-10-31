from rest_framework.permissions import BasePermission

from accounts.models import RoleChoices


class IsAdminRole(BasePermission):
    """Role comes from the JWT-resolved account, never from a client-supplied id."""

    message = 'User is not an admin.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated
                    and request.user.role == RoleChoices.ADMIN)
