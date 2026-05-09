from django.urls import path
from . import views

urlpatterns = [
    # User Authentication endpoints
    # Anyone can access these - no token required
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),

    # Device Management endpoints
    # GET - retrieve all devices for logged in user
    # POST - register a new device
    path('devices/', views.devices, name='devices'),

    # Send ON/OFF command to a specific device (used by mobile app)
    path('devices/<int:device_id>/control/', views.control_device, name='control_device'),

    # ESP32 polls this endpoint to check for pending commands
    path('devices/<int:device_id>/command/', views.get_pending_command, name='get_pending_command'),

    # Energy Data endpoints
    # POST - ESP32 sends sensor readings to backend
    path('energy/', views.receive_energy_data, name='receive_energy_data'),

    # GET - mobile app retrieves energy history for a specific device
    path('energy/<int:device_id>/', views.energy_history, name='energy_history'),

    # Safety Alerts endpoint
    # GET - mobile app retrieves all safety alerts for logged in user
    path('alerts/', views.safety_alerts, name='safety_alerts'),
    
    path('reset-admin/', views.reset_admin_password, name='reset_admin'),
]