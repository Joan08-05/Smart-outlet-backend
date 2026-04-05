from django.contrib import admin
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule

# Register all models to make them visible in the Django admin panel
admin.site.register(User)
admin.site.register(Device)
admin.site.register(EnergyRecord)
admin.site.register(ControlLog)
admin.site.register(SafetyAlert)
admin.site.register(ApplianceSchedule)
