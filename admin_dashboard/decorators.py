from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/admin-dashboard/login/')
        if not (request.user.is_staff or request.user.role == 'admin'):
            messages.error(request, 'Accès refusé. Réservé aux administrateurs.')
            return redirect('/admin-dashboard/login/')
        return view_func(request, *args, **kwargs)
    return wrapper
