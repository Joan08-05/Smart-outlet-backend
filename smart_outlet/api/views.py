from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Q
from .models import User, Device, EnergyRecord, ControlLog, SafetyAlert, ApplianceSchedule
from .serializers import (UserRegistrationSerializer, DeviceSerializer,
                          EnergyRecordSerializer, ControlLogSerializer,
                          SafetyAlertSerializer, ApplianceScheduleSerializer,
                          UserProfileSerializer)
import secrets
import string
from django.contrib.auth.hashers import make_password, check_password


# ─── USER AUTHENTICATION ───────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    """
    Registers a new user.
    Accepts: first_name, last_name, username, email, password, phone
    Returns: success message
    Security: password is automatically hashed before saving
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
    Records last login time for the user
    """
    username = request.data.get('username')
    password = request.data.get('password')

    user = authenticate(username=username, password=password)

    if user:
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
          Auto-deletes expired unclaimed devices before returning
          Automatically checks and applies active schedules
    POST - Registers a new device, generates a 6-char claim code for ESP32
           Claim code expires in 15 minutes
           Returns claim code in response for frontend to show to user
    """
    if request.method == 'GET':
        now = timezone.now()

        # Auto-delete expired unclaimed devices
        # If claim code expired and ESP32 never claimed the device, remove it
        Device.objects.filter(
            user=request.user,
            is_claimed=False,
            claim_code_expires_at__lt=now
        ).delete()

        # Now get remaining valid devices
        user_devices = Device.objects.filter(user=request.user)

        # Check and apply active schedules for each device
        for device in user_devices:
            active_schedule = ApplianceSchedule.objects.filter(
                device=device,
                status='active'
            ).filter(
                Q(start_time__isnull=True) | Q(start_time__lte=now)
            ).filter(
                Q(end_time__isnull=True) | Q(end_time__gte=now)
            ).first()

            if active_schedule:
                if device.status != 'ON':
                    device.status = 'ON'
                    device.save()
                    ControlLog.objects.create(
                        device=device,
                        action='ON',
                        control_source='schedule'
                    )
            else:
                was_scheduled_on = ControlLog.objects.filter(
                    device=device,
                    action='ON',
                    control_source='schedule'
                ).order_by('-timestamp').first()

                was_manually_turned_on = ControlLog.objects.filter(
                    device=device,
                    action='ON',
                    control_source='mobile_app'
                ).order_by('-timestamp').first()

                if device.status == 'ON' and was_scheduled_on:
                    if not was_manually_turned_on or was_scheduled_on.timestamp > was_manually_turned_on.timestamp:
                        device.status = 'OFF'
                        device.save()
                        ControlLog.objects.create(
                            device=device,
                            action='OFF',
                            control_source='schedule_ended'
                        )

        # Refresh queryset after schedule updates
        user_devices = Device.objects.filter(user=request.user)
        serializer = DeviceSerializer(user_devices, many=True)
        return Response({
            'total_devices': user_devices.count(),
            'devices': serializer.data
        })

    if request.method == 'POST':
        serializer = DeviceSerializer(data=request.data)
        if serializer.is_valid():
            # Generate a 6 character claim code for ESP32 provisioning
            claim_code = ''.join(secrets.choice(
                string.ascii_uppercase + string.digits
            ) for _ in range(6))

            # Set claim code expiry to 15 minutes from now
            expires_at = timezone.now() + timezone.timedelta(minutes=15)

            # Save device with claim code
            device = serializer.save(
                user=request.user,
                claim_code=claim_code,
                claim_code_expires_at=expires_at,
                is_claimed=False
            )

            # Return device data plus claim code for frontend to show user
            response_data = serializer.data
            response_data['claim_code'] = claim_code
            response_data['claim_code_expires_in'] = '15 minutes'

            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def control_device(request, device_id):
    """
    Receives ON/OFF command from the mobile application.
    Stores the command and logs the control action.
    Security: users can only control their own devices
    """
    try:
        device = Device.objects.get(id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    action = request.data.get('action')

    if action not in ['ON', 'OFF']:
        return Response(
            {'error': 'Action must be ON or OFF'},
            status=status.HTTP_400_BAD_REQUEST
        )

    device.status = action
    device.save()

    ControlLog.objects.create(
        device=device,
        action=action,
        control_source='mobile_app'
    )

    return Response({'message': f'Device turned {action}', 'status': action})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def regenerate_claim_code(request, device_id):
    """
    Generates a new claim code for a device whose previous code expired.
    Only works if the device has not already been claimed by an ESP32.
    """
    try:
        device = Device.objects.get(id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if device.is_claimed:
        return Response(
            {'error': 'Device is already claimed. Cannot regenerate claim code.'},
            status=status.HTTP_409_CONFLICT
        )

    new_claim_code = ''.join(secrets.choice(
        string.ascii_uppercase + string.digits
    ) for _ in range(6))

    device.claim_code = new_claim_code
    device.claim_code_expires_at = timezone.now() + timezone.timedelta(minutes=15)
    device.save()

    return Response({
        'claim_code': new_claim_code,
        'claim_code_expires_in': '15 minutes'
    })


# ─── DEVICE CLAIMING ───────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def claim_device(request):
    """
    ESP32 exchanges a one-time claim code for a permanent device secret.
    No authentication required - device has no token yet.
    Accepts: claim_code
    Returns: device_id and device_secret (shown only once)
    Errors: 404 not found, 409 already claimed, 410 expired
    """
    claim_code = request.data.get('claim_code', '').strip().upper()

    if not claim_code:
        return Response(
            {'error': 'claim_code is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        device = Device.objects.get(claim_code=claim_code)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Invalid claim code'},
            status=status.HTTP_404_NOT_FOUND
        )

    if device.is_claimed:
        return Response(
            {'error': 'Device already claimed'},
            status=status.HTTP_409_CONFLICT
        )

    if device.claim_code_expires_at and timezone.now() > device.claim_code_expires_at:
        return Response(
            {'error': 'Claim code has expired. Please regenerate from the app.'},
            status=status.HTTP_410_GONE
        )

    # Generate permanent device secret
    device_secret = secrets.token_urlsafe(32)

    # Store hashed secret, mark as claimed, clear claim code
    device.device_secret_hash = make_password(device_secret)
    device.is_claimed = True
    device.claim_code = None
    device.claim_code_expires_at = None
    device.save()

    return Response({
        'device_id': device.id,
        'device_secret': device_secret
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def device_auth(request):
    """
    ESP32 authenticates using device_id and device_secret.
    No user username/password needed - more secure for IoT devices.
    Returns JWT tokens scoped to the device owner's account.
    """
    device_id = request.data.get('device_id')
    device_secret = request.data.get('device_secret', '')

    if not device_id or not device_secret:
        return Response(
            {'error': 'device_id and device_secret are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        device = Device.objects.get(id=device_id, is_claimed=True)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found or not claimed'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not device.device_secret_hash or not check_password(device_secret, device.device_secret_hash):
        return Response(
            {'error': 'Invalid device secret'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    refresh = RefreshToken.for_user(device.user)
    refresh['device_id'] = device.id
    refresh['scope'] = 'device'

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
    })


# ─── ENERGY DATA ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def receive_energy_data(request):
    """
    Receives sensor readings from the ESP32 microcontroller.
    Accepts: device, voltage, current, power, energy_kwh
    Simply stores the reading - safety detection is handled by ESP32
    firmware. ESP32 reports detected faults via POST /api/alerts/report/
    """
    serializer = EnergyRecordSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'message': 'Energy data saved'}, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
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

    records = EnergyRecord.objects.filter(device=device).order_by('-timestamp')
    serializer = EnergyRecordSerializer(records, many=True)
    return Response(serializer.data)


# ─── SAFETY ALERTS ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def safety_alerts(request):
    """
    Returns all safety alerts for all devices belonging to the logged in user.
    Alerts are created by the ESP32 reporting its own detected faults
    via POST /api/alerts/report/
    Results are ordered by most recent first.
    """
    user_devices = Device.objects.filter(user=request.user)
    alerts = SafetyAlert.objects.filter(
        device__in=user_devices
    ).order_by('-timestamp')
    serializer = SafetyAlertSerializer(alerts, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def report_safety_alert(request):
    """
    ESP32 reports a safety event it has already detected and acted on.
    The ESP32 makes the safety decision - this endpoint simply logs it
    so the user can see it in the mobile application.
    Accepts: device, alert_type, measured_value, threshold_value, action_taken
    alert_type options: OVERLOAD, OVERVOLTAGE, UNDERVOLTAGE
    """
    device_id = request.data.get('device')
    alert_type = request.data.get('alert_type')
    measured_value = request.data.get('measured_value')
    threshold_value = request.data.get('threshold_value')
    action_taken = request.data.get('action_taken', 'Relay disconnected')

    if not device_id or not alert_type or measured_value is None or threshold_value is None:
        return Response(
            {'error': 'device, alert_type, measured_value, and threshold_value are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    alert = SafetyAlert.objects.create(
        device=device,
        alert_type=alert_type,
        measured_value=measured_value,
        threshold_value=threshold_value,
        action_taken=action_taken
    )

    return Response({
        'message': 'Safety alert logged successfully',
        'alert_id': alert.id
    }, status=status.HTTP_201_CREATED)


# ─── ESP32 POLLING ─────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pending_command(request, device_id):
    """
    Polled by ESP32 every few seconds.
    Checks active schedules first - both start_time and end_time are optional.
    If no start_time - schedule is immediately active.
    If no end_time - schedule runs indefinitely.
    Otherwise returns the manually set device status.
    repeat_pattern values: daily, weekly, once, or blank for no repeat
    """
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    now = timezone.now()

    active_schedule = ApplianceSchedule.objects.filter(
        device=device,
        status='active'
    ).filter(
        Q(start_time__isnull=True) | Q(start_time__lte=now)
    ).filter(
        Q(end_time__isnull=True) | Q(end_time__gte=now)
    ).first()

    if active_schedule:
        scheduled_status = 'ON'

        if device.status != scheduled_status:
            device.status = scheduled_status
            device.save()
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

    was_scheduled_on = ControlLog.objects.filter(
        device=device,
        action='ON',
        control_source='schedule'
    ).order_by('-timestamp').first()

    was_manually_turned_on = ControlLog.objects.filter(
        device=device,
        action='ON',
        control_source='mobile_app'
    ).order_by('-timestamp').first()

    if device.status == 'ON' and was_scheduled_on:
        if not was_manually_turned_on or was_scheduled_on.timestamp > was_manually_turned_on.timestamp:
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

    return Response({'status': device.status})


# ─── ADMIN RESET ───────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def reset_admin_password(request):
    """
    Emergency admin creation endpoint - protected by secret key
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()

    if request.data.get('secret') != 'joan2026smart':
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    if not User.objects.filter(is_superuser=True).exists():
        User.objects.create_superuser(
            username='admin',
            email='admin@smartoutlet.com',
            password='SmartAdmin2026!'
        )
        return Response({'message': 'Superuser created'})

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
    Both start_time and end_time are optional.
    repeat_pattern options: daily, weekly, once, or leave blank for no repeat
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
    Used by ESP32 to check scheduled operations
    """
    try:
        device = Device.objects.get(id=device_id)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    active_schedules = ApplianceSchedule.objects.filter(
        device=device,
        status='active'
    )
    serializer = ApplianceScheduleSerializer(active_schedules, many=True)
    return Response(serializer.data)


# ─── FULL HISTORY ──────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def all_energy_history(request):
    """
    GET - Returns ALL energy records for ALL devices belonging to logged in user
    Ordered by most recent first
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

# ─── USER PROFILE ──────────────────────────────────────────────────

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    GET - Returns the logged in user's profile details
    PATCH - Updates the logged in user's profile
    Accepts: username, email, phone, location
    User is identified from JWT token - no ID needed in URL
    """
    if request.method == 'GET':
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)

    if request.method == 'PATCH':
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True  # Allow partial updates - not all fields required
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                'message': 'Profile updated successfully',
                'username': request.user.username,
                'email': request.user.email,
                'phone': request.user.phone,
                'location': request.user.location,
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── DELETE AND RENAME DEVICE ──────────────────────────────────────

@api_view(['DELETE', 'PATCH'])
@permission_classes([IsAuthenticated])
def device_detail(request, device_id):
    """
    DELETE - Permanently removes a device and all its associated data
             Security: users can only delete their own devices
    PATCH - Updates device_name only, keeps everything else unchanged
            Security: users can only rename their own devices
    """
    try:
        device = Device.objects.get(id=device_id, user=request.user)
    except Device.DoesNotExist:
        return Response(
            {'error': 'Device not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'DELETE':
        device.delete()
        return Response({'message': 'Device deleted successfully'})

    if request.method == 'PATCH':
        # Only allow updating device_name
        device_name = request.data.get('device_name')
        if not device_name:
            return Response(
                {'error': 'device_name is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        device.device_name = device_name
        device.save()
        serializer = DeviceSerializer(device)
        return Response(serializer.data)