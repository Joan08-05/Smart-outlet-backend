from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.core.validators import RegexValidator
from django.contrib.auth.password_validation import validate_password
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    # Email must be unique - returns a clean 400 error instead of a database crash
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message='This email is already registered.'
            )
        ]
    )

    # Tanzania phone number validation - accepts +255XXXXXXXXX or 0XXXXXXXXX
    phone = serializers.CharField(
        required=False,
        allow_blank=True,
        validators=[
            RegexValidator(
                regex=r'^(\+255|0)[67]\d{8}$',
                message='Enter a valid Tanzanian phone number. Example: +255712345678 or 0712345678'
            )
        ]
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'phone']

    def validate_password(self, value):
        """
        Password must be strong - at least 8 characters,
        must contain uppercase, lowercase, number and special character
        """
        import re
        if len(value) < 8:
            raise serializers.ValidationError(
                'Password must be at least 8 characters long.'
            )
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError(
                'Password must contain at least one uppercase letter.'
            )
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError(
                'Password must contain at least one lowercase letter.'
            )
        if not re.search(r'\d', value):
            raise serializers.ValidationError(
                'Password must contain at least one number.'
            )
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError(
                'Password must contain at least one special character (!@#$%^&* etc).'
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        # user is NOT included - it is set automatically from the JWT token
        fields = ['id', 'device_name', 'location', 'firmware_version', 'status', 'installation_date']
        read_only_fields = ['installation_date']


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
        read_only_fields = ['timestamp', 'resolved_at']

    def validate_alert_type(self, value):
        """
        Validates that the alert type is one of the four types
        determined by the ESP32. The backend does not classify
        or rename alert types - it stores exactly what the ESP32 sends.
        Valid types: undervoltage, overvoltage, overcurrent, overload
        """
        valid_types = ['undervoltage', 'overvoltage', 'overcurrent', 'overload']
        if value.lower() not in valid_types:
            raise serializers.ValidationError(
                f'Invalid alert type. Must be one of: {", ".join(valid_types)}'
            )
        return value.lower()


class ApplianceScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplianceSchedule
        fields = '__all__'

    def validate_repeat_pattern(self, value):
        """
        Only two valid repeat patterns:
        - none: schedule runs once then becomes inactive
        - daily: schedule repeats every day at same time
        """
        valid = ['none', 'daily']
        normalized = value.lower().strip()
        if normalized not in valid:
            raise serializers.ValidationError(
                f'Invalid repeat pattern. Must be one of: {", ".join(valid)}'
            )
        return normalized


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone', 'location', 'first_name', 'last_name']