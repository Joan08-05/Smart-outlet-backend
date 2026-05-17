from django.contrib import admin
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['id', 'device_name', 'location', 'status', 'user']

@admin.register(EnergyRecord)
class EnergyRecordAdmin(admin.ModelAdmin):
    list_display = ['id', 'device', 'voltage', 'current', 'power', 'timestamp']

@admin.register(SafetyAlert)
class SafetyAlertAdmin(admin.ModelAdmin):
    list_display = ['id', 'device', 'alert_type', 'measured_value', 'timestamp']

@admin.register(ControlLog)
class ControlLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'device', 'action', 'control_source', 'timestamp']

admin.site.register(User)
admin.site.register(ApplianceSchedule)
