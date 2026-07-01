from django.urls import path
from . import views

urlpatterns = [
    # ─── USER AUTHENTICATION ───────────────────────────────────────
    # Anyone can access these - no token required
    path('auth/register/', views.register, name='register'),
    path('auth/login/', views.login, name='login'),

    # ─── DEVICE CLAIMING ───────────────────────────────────────────
    # ESP32 provisioning - no token required
    # IMPORTANT: these must come BEFORE devices/<int:device_id>/ paths
    path('devices/claim/', views.claim_device, name='claim_device'),
    path('devices/auth/', views.device_auth, name='device_auth'),
    path('devices/<int:device_id>/regenerate-claim/', views.regenerate_claim_code, name='regenerate_claim_code'),
    

    # ─── DEVICE MANAGEMENT ─────────────────────────────────────────
    # GET - retrieve all devices for logged in user
    # POST - register a new device and generate claim code
    path('devices/', views.devices, name='devices'),

    # Send ON/OFF command to a specific device (used by mobile app)
    path('devices/<int:device_id>/control/', views.control_device, name='control_device'),

    # ESP32 polls this endpoint to check for pending commands
    path('devices/<int:device_id>/command/', views.get_pending_command, name='get_pending_command'),

    # ─── ENERGY DATA ───────────────────────────────────────────────
    # POST - ESP32 sends sensor readings to backend
    path('energy/', views.receive_energy_data, name='receive_energy_data'),

    # IMPORTANT - energy/history/ must come BEFORE energy/<int:device_id>/
    # GET - mobile app retrieves ALL energy history for ALL devices
    path('energy/history/', views.all_energy_history, name='all_energy_history'),

    # GET - mobile app retrieves energy history for a specific device
    path('energy/<int:device_id>/', views.energy_history, name='energy_history'),

    # ─── SAFETY ALERTS ─────────────────────────────────────────────
    # GET - mobile app retrieves all safety alerts for logged in user
    path('alerts/', views.safety_alerts, name='safety_alerts'),
    
    # POST - ESP32 reports a safety alert it has already detected
    path('alerts/report/', views.report_safety_alert, name='report_safety_alert'),

    # ─── SCHEDULING ────────────────────────────────────────────────
    # GET - retrieve all schedules for logged in user
    # POST - create a new schedule
    path('schedules/', views.schedules, name='schedules'),

    # DELETE - delete a specific schedule
    path('schedules/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),

    # GET - retrieve active schedules for a specific device (used by ESP32)
    path('schedules/device/<int:device_id>/', views.device_schedules, name='device_schedules'),

    # ─── HISTORY ───────────────────────────────────────────────────
    # GET - retrieve full ON/OFF history for all devices of logged in user
    path('control-logs/', views.control_logs_history, name='control_logs_history'),

    # ─── ADMIN ─────────────────────────────────────────────────────
    # Emergency admin reset endpoint - protected by secret key
    path('reset-admin/', views.reset_admin_password, name='reset_admin'),
    # ─── USER PROFILE ──────────────────────────────────────────────────
    # GET - get logged in user profile
    # PATCH - update logged in user profile
    path('users/profile/', views.user_profile, name='user_profile'),

    # ─── DEVICE DETAIL ─────────────────────────────────────────────────
    # DELETE - permanently delete a device
    # PATCH - rename a device
    path('devices/<int:device_id>/', views.device_detail, name='device_detail'),
]