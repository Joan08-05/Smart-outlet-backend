from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule
from .serializers import (UserRegistrationSerializer, DeviceSerializer, 
                          EnergyRecordSerializer, ControlLogSerializer, 
                          SafetyAlertSerializer, ApplianceScheduleSerializer)

# ─── SAFETY THRESHOLDS ─────────────────────────────────────────────
# Based on Tanzanian electrical standards (230V AC) and project scope (max 3000W)
POWER_THRESHOLD = 3000   # watts - maximum safe power load
VOLTAGE_THRESHOLD = 260  # volts - above Tanzania standard of 230V


# ─── USER AUTHENTICATION ───────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])  # No token required - anyone can register
def register(request):
    """
    Registers a new user.
    Accepts: full_name, username, email, password, phone
    Returns: success message
    Security: password is automatically hashed before saving - never stored as plain text
    """
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {'message': 'User registered successfully'}, 
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    Logs in an existing user.
    Accepts: username, password
    Returns: access token and refresh token
    Also records the last login time for the user
    """
    username = request.data.get('username')
    password = request.data.get('password')
    
    user = authenticate(username=username, password=password)
    
    if user:
        # Record last login time
        from django.utils import timezone
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    return Response(
        {'error': 'Invalid credentials'}, 
        status=status.HTTP_401_UNAUTHORIZED
    )


# ─── DEVICE MANAGEMENT ─────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def devices(request):
    """
    GET - Returns all devices belonging to the logged in user
          Automatically checks and applies active schedules before returning
    POST - Registers a new device and links it to the logged in user
    """
    if request.method == 'GET':
        from django.utils import timezone
        from django.db.models import Q
        
        now = timezone.now()
        user_devices = Device.objects.filter(user=request.user)
        
        # Check schedules for each device and update status if needed
        for device in user_devices:
            
            # Check if there's an active schedule right now
            active_schedule = ApplianceSchedule.objects.filter(
                device=device,
                status='active',
                start_time__lte=now
            ).filter(
                Q(end_time__isnull=True) | Q(end_time__gte=now)
            ).first()
            
            if active_schedule:
                # Schedule is active - device should be ON
                if device.status != 'ON':
                    device.status = 'ON'
                    device.save()
                    ControlLog.objects.create(
                        device=device,
                        action='ON',
                        control_source='schedule'
                    )
            else:
                # Check if a schedule just ended recently (within last 30 seconds)
                just_ended = ApplianceSchedule.objects.filter(
                    device=device,
                    status='active',
                    end_time__isnull=False,
                    end_time__lte=now,
                    end_time__gte=now - timezone.timedelta(seconds=30)
                ).first()
                
                if just_ended and device.status == 'ON':
                    device.status = 'OFF'
                    device.save()
                    ControlLog.objects.create(
                        device=device,
                        action='OFF',
                        control_source='schedule_ended'
                    )
        
        # Now return updated devices
        user_devices = Device.objects.filter(user=request.user)
        serializer = DeviceSerializer(user_devices, many=True)
        return Response({
            'total_devices': user_devices.count(),
            'devices': serializer.data
        })
    
    if request.method == 'POST':
        serializer = DeviceSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])  # JWT token required
def control_device(request, device_id):
    """
    Receives ON/OFF command from the mobile application.
    Stores the command and logs the control action.
    The ESP32 will poll the get_pending_command endpoint to retrieve this status.
    Security: users can only control their own devices
    """
    # Make sure the device belongs to the logged in user
    try:
        device = Device.objects.get(id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    action = request.data.get('action')
    
    # Only accept valid commands
    if action not in ['ON', 'OFF']:
        return Response(
            {'error': 'Action must be ON or OFF'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update device status in database
    device.status = action
    device.save()
    
    # Log every control action for traceability
    ControlLog.objects.create(
        device=device,
        action=action,
        control_source='mobile_app'  # Command came from mobile application
    )
    
    return Response({'message': f'Device turned {action}', 'status': action})


# ─── ENERGY DATA ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])  # JWT token required
def receive_energy_data(request):
    """
    Receives sensor readings from the ESP32 microcontroller.
    Accepts: device_id, voltage, current, power, energy_kwh
    After saving, automatically checks safety thresholds.
    If thresholds are exceeded, a safety alert is created and returned.
    This implements the backend safety alert logic from the system design.
    """
    serializer = EnergyRecordSerializer(data=request.data)
    if serializer.is_valid():
        energy_record = serializer.save()
        
        # ── SAFETY CHECK ──────────────────────────────────────────
        # Check every incoming reading against defined safety thresholds
        alerts = []
        
        # Check for overload (power exceeds 3000W limit)
        if energy_record.power > POWER_THRESHOLD:
            SafetyAlert.objects.create(
                device=energy_record.device,
                alert_type='OVERLOAD',
                measured_value=energy_record.power,
                threshold_value=POWER_THRESHOLD,
                action_taken='Alert sent to user'
            )
            alerts.append('OVERLOAD detected')
        
        # Check for overvoltage (voltage exceeds 260V)
        if energy_record.voltage > VOLTAGE_THRESHOLD:
            SafetyAlert.objects.create(
                device=energy_record.device,
                alert_type='OVERVOLTAGE',
                measured_value=energy_record.voltage,
                threshold_value=VOLTAGE_THRESHOLD,
                action_taken='Alert sent to user'
            )
            alerts.append('OVERVOLTAGE detected')
        
        # Return response with any alerts triggered
        response_data = {'message': 'Energy data saved'}
        if alerts:
            response_data['alerts'] = alerts
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])  # JWT token required
def energy_history(request, device_id):
    """
    Returns historical energy records for a specific device.
    Results are ordered by most recent first.
    Security: users can only view energy history for their own devices
    """
    try:
        device = Device.objects.get(id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get all energy records for this device, newest first
    records = EnergyRecord.objects.filter(device=device).order_by('-timestamp')
    serializer = EnergyRecordSerializer(records, many=True)
    return Response(serializer.data)


# ─── SAFETY ALERTS ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # JWT token required
def safety_alerts(request):
    """
    Returns all safety alerts for all devices belonging to the logged in user.
    Results are ordered by most recent first.
    Security: users can only see alerts for their own devices
    """
    # Get all devices for this user first
    user_devices = Device.objects.filter(user=request.user)
    
    # Then get all alerts for those devices
    alerts = SafetyAlert.objects.filter(
        device__in=user_devices
    ).order_by('-timestamp')
    
    serializer = SafetyAlertSerializer(alerts, many=True)
    return Response(serializer.data)


# ─── ESP32 POLLING ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_command(request, device_id):
    """
    Polled by ESP32 every few seconds.
    Checks active schedules first - if current time falls within a schedule,
    returns the scheduled status and updates the device.
    Handles schedules with no end time (e.g. fridge - runs indefinitely).
    Handles schedules with end time (e.g. fan - runs until set time).
    Otherwise returns the manually set device status.
    """
    from django.utils import timezone
    from django.db.models import Q

    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    now = timezone.now()

    # Check if current time falls within any active schedule
    # Handles both schedules with end_time and without end_time
    active_schedule = ApplianceSchedule.objects.filter(
        device=device,
        status='active',
        start_time__lte=now
    ).filter(
        Q(end_time__isnull=True) | Q(end_time__gte=now)
    ).first()

    if active_schedule:
        # Schedule is active right now - turn ON
        scheduled_status = 'ON'

        # Update device status if it changed
        if device.status != scheduled_status:
            device.status = scheduled_status
            device.save()

            # Log the scheduled action
            ControlLog.objects.create(
                device=device,
                action=scheduled_status,
                control_source='schedule'
            )

        return Response({
            'status': scheduled_status,
            'source': 'schedule',
            'schedule_ends': active_schedule.end_time
        })

    # No active schedule - check if a schedule just ended (within last 10 seconds)
    just_ended = ApplianceSchedule.objects.filter(
        device=device,
        status='active',
        end_time__isnull=False,
        end_time__lte=now,
        end_time__gte=now - timezone.timedelta(seconds=10)
    ).first()

    if just_ended:
        # Schedule just ended - turn device OFF
        if device.status == 'ON':
            device.status = 'OFF'
            device.save()

            ControlLog.objects.create(
                device=device,
                action='OFF',
                control_source='schedule_ended'
            )

        return Response({
            'status': 'OFF',
            'source': 'schedule_ended'
        })

    # No schedule involved - return current manually set device status
    return Response({'status': device.status})

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_admin_password(request):
    """
    Emergency admin creation endpoint - protected by secret key
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Secret key check - only you know this
    if request.data.get('secret') != 'joan2026smart':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)
    
    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@smartoutlet.com',
            password='SmartAdmin2026!'
        )
        return Response({'message': 'Superuser created'})
    
    # Reset password if user exists
    user = User.objects.get(username='admin')
    user.set_password('SmartAdmin2026!')
    user.save()
    return Response({'message': 'Password reset successfully'})
# ─── SCHEDULING ────────────────────────────────────────────────────

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def schedules(request):
    """
    GET - Returns all schedules for devices belonging to the logged in user
    POST - Creates a new schedule for a device
    Accepts: device, start_time, end_time, repeat_pattern, status
    Example: {"device": 1, "start_time": "2026-05-17T08:00:00Z", "end_time": "2026-05-17T10:00:00Z", "repeat_pattern": "daily", "status": "active"}
    """
    if request.method == 'GET':
        user_devices = Device.objects.filter(user=request.user)
        user_schedules = ApplianceSchedule.objects.filter(device__in=user_devices)
        serializer = ApplianceScheduleSerializer(user_schedules, many=True)
        return Response(serializer.data)
    
    if request.method == 'POST':
        serializer = ApplianceScheduleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_schedule(request, schedule_id):
    """
    DELETE - Deletes a specific schedule
    Security: users can only delete schedules for their own devices
    """
    try:
        user_devices = Device.objects.filter(user=request.user)
        schedule = ApplianceSchedule.objects.get(id=schedule_id, device__in=user_devices)
    except ApplianceSchedule.DoesNotExist:
        return Response({'error': 'Schedule not found'}, status=status.HTTP_404_NOT_FOUND)
    
    schedule.delete()
    return Response({'message': 'Schedule deleted successfully'})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_schedules(request, device_id):
    """
    GET - Returns active schedules for a specific device
    Used by ESP32 to check if any scheduled ON/OFF should be executed
    """
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )
    
    schedules = ApplianceSchedule.objects.filter(
        device=device,
        status='active'
    )
    serializer = ApplianceScheduleSerializer(schedules, many=True)
    return Response(serializer.data)

# ─── FULL HISTORY ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_energy_history(request):
    """
    GET - Returns ALL energy records for ALL devices belonging to logged in user
    Ordered by most recent first
    Useful for displaying full energy history dashboard
    """
    user_devices = Device.objects.filter(user=request.user)
    records = EnergyRecord.objects.filter(
        device__in=user_devices
    ).order_by('-timestamp')
    serializer = EnergyRecordSerializer(records, many=True)
    return Response({
        'total_records': records.count(),
        'energy_history': serializer.data
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def control_logs_history(request):
    """
    GET - Returns ALL control logs for ALL devices belonging to logged in user
    Shows history of every ON/OFF action - manual and scheduled
    Ordered by most recent first
    """
    user_devices = Device.objects.filter(user=request.user)
    logs = ControlLog.objects.filter(
        device__in=user_devices
    ).order_by('-timestamp')
    serializer = ControlLogSerializer(logs, many=True)
    return Response({
        'total_logs': logs.count(),
        'control_logs': serializer.data
    })