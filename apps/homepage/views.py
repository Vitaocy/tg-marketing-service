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
                "stats": dto.stats.__dict__,
                "channels": [c.__dict__ for c in dto.channels],
                "ai_insights": [i.__dict__ for i in dto.ai_insights],
                "collections": [c.__dict__ for c in dto.collections],
                "csrfToken": get_token(request),
            }
        )