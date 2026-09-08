from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/voice/", include("apps.voice.urls")),
    path("api/banking/", include("apps.banking.urls")),
    path("api/schemes/", include("apps.schemes.urls")),
    path("api/literacy/", include("apps.literacy.urls")),
    path("api/fraud/", include("apps.fraud.urls")),
    path("api/vision/", include("apps.vision.urls")),
    path("api/sync/", include("apps.sync.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
