from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    def __str__(self):
        return self.email


class Device(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True, null=True)
    firmware_version = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default='offline')
    installation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.device_name


class EnergyRecord(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    voltage = models.FloatField()
    current = models.FloatField()
    power = models.FloatField()
    energy_kwh = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.device_name} - {self.timestamp}"


class ControlLog(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    action = models.CharField(max_length=10)
    control_source = models.CharField(max_length=20)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.device.device_name} - {self.action}"


class SafetyAlert(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=50)
    measured_value = models.FloatField()
    threshold_value = models.FloatField()
    action_taken = models.CharField(max_length=100, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alert_type} - {self.device.device_name}"


class ApplianceSchedule(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    repeat_pattern = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, default='active')

    def __str__(self):
        return f"{self.device.device_name} schedule"
    