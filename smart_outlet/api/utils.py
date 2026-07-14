from django.utils import timezone


def get_active_schedule_for_device(device, now=None):
    """
    Returns the currently active ApplianceSchedule for a device, or None.
    Handles all repeat_pattern values: none, daily, weekly, weekdays, weekends.
    start_time and end_time are both optional in every pattern.
    """
    from .models import ApplianceSchedule  # avoid circular import

    if now is None:
        now = timezone.now()

    current_time = now.time()
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday

    all_schedules = ApplianceSchedule.objects.filter(
        device=device,
        status='active'
    )

    for schedule in all_schedules:
        repeat = (schedule.repeat_pattern or 'none').lower().strip()

        if repeat == 'daily':
            schedule_start = schedule.start_time.time() if schedule.start_time else None
            schedule_end = schedule.end_time.time() if schedule.end_time else None
            if schedule_start and schedule_end:
                if schedule_start <= current_time <= schedule_end:
                    return schedule
            elif schedule_start and not schedule_end:
                if current_time >= schedule_start:
                    return schedule
            elif not schedule_start and schedule_end:
                if current_time <= schedule_end:
                    return schedule
            elif not schedule_start and not schedule_end:
                return schedule

        elif repeat == 'weekly':
            if schedule.start_time:
                schedule_day = schedule.start_time.weekday()
                schedule_start_time = schedule.start_time.time()
                schedule_end_time = schedule.end_time.time() if schedule.end_time else None
                if current_weekday == schedule_day:
                    if schedule_end_time:
                        if schedule_start_time <= current_time <= schedule_end_time:
                            return schedule
                    else:
                        if current_time >= schedule_start_time:
                            return schedule

        elif repeat == 'weekdays':
            if current_weekday <= 4:
                schedule_start = schedule.start_time.time() if schedule.start_time else None
                schedule_end = schedule.end_time.time() if schedule.end_time else None
                if schedule_start and schedule_end:
                    if schedule_start <= current_time <= schedule_end:
                        return schedule
                elif schedule_start:
                    if current_time >= schedule_start:
                        return schedule

        elif repeat == 'weekends':
            if current_weekday >= 5:
                schedule_start = schedule.start_time.time() if schedule.start_time else None
                schedule_end = schedule.end_time.time() if schedule.end_time else None
                if schedule_start and schedule_end:
                    if schedule_start <= current_time <= schedule_end:
                        return schedule
                elif schedule_start:
                    if current_time >= schedule_start:
                        return schedule

        else:
            # none or blank - full datetime comparison (runs once)
            start_ok = schedule.start_time is None or schedule.start_time <= now
            end_ok = schedule.end_time is None or schedule.end_time >= now
            if start_ok and end_ok:
                return schedule

    return None
