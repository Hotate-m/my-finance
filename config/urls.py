from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from app_finance import views as finance_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", finance_views.logout_view, name="logout"),
    path("", include("app_finance.urls", namespace="app_finance")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)