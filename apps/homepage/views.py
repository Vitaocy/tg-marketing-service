from django.middleware.csrf import get_token
from django.shortcuts import redirect
from django.views import View
from inertia import render as inertia_render

from .services.dashboard_service import DashboardService


class DashboardView(View):

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('main_index')

        service = DashboardService(request.user)
        dto = service.build()

        return inertia_render(
            request,
            'Dashboard',
            props={
                **dto.model_dump(mode="json"),
                "csrfToken": get_token(request),
            }
        )