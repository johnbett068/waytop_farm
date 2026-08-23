from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.shortcuts import render


class StaffLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        if not form.get_user().is_staff:
            form.add_error(None, "Invalid staff credentials.")
            return self.form_invalid(form)
        return super().form_valid(form)


@login_required
def profile(request):
    if not request.user.is_active or not request.user.is_staff:
        raise PermissionDenied
    return render(request, "accounts/profile.html")

