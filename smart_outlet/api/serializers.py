from rest_framework import serializers
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'phone']

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = '__all__'
        read_only_fields = ['user', 'installation_date']


class EnergyRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnergyRecord
        fields = '__all__'
        read_only_fields = ['timestamp']


class ControlLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ControlLog
        fields = '__all__'
        read_only_fields = ['timestamp']


class SafetyAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SafetyAlert
        fields = '__all__'
        read_only_fields = ['timestamp']


class ApplianceScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplianceSchedule
        fields = '__all__'