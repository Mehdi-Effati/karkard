from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html',
        redirect_authenticated_user=True,
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', views.calendar_view, name='calendar'),
    path('api/day/save/', views.save_day, name='save_day'),
    path('api/day/delete/', views.delete_day, name='delete_day'),
]
