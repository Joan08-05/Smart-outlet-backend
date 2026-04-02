"""
URL configuration for smart_outlet project.
All API endpoints are prefixed with /api/
JWT token endpoints are available at /api/token/
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    # Django admin panel - for managing database through browser
    path('admin/', admin.site.urls),
    
    # All API endpoints from api/urls.py are connected here
    # Example: /api/auth/register/, /api/devices/, /api/energy/ etc.
    path('api/', include('api.urls')),
    
    # JWT token refresh endpoint
    # Used when the access token expires and needs to be renewed
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]