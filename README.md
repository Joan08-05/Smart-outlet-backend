**Live API URL:** https://smart-outlet-backend.onrender.com

# Smart Electric Outlet Backend

A cloud-based Django REST API backend for a Smart Electric Outlet IoT system built for Tanzanian domestic households.

Built by **Joan Charlestino Mwihava** as part of a Final Year Project at the University of Dar es Salaam (UDSM), College of Information and Communication Technologies.

---

## What This Backend Does

This backend acts as the central bridge between the ESP32 microcontroller (hardware) and the Flutter mobile application (frontend). It is responsible for:

- Receiving real-time energy data from the ESP32 microcontroller
- Processing and storing energy records in a PostgreSQL database
- Allowing users to remotely control their appliances via the mobile app
- Provisioning ESP32 devices securely without ever storing user account credentials on the hardware
- Running automatic scheduling logic (daily, weekly, or one-time ON/OFF operations)
- Receiving and logging safety alerts detected locally by the ESP32
- Managing user authentication securely using JWT tokens

---

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Python | 3.14 | Programming language |
| Django | 6.0.3 | Web framework |
| Django REST Framework | 3.17.1 | API development |
| djangorestframework-simplejwt | 5.5.1 | JWT authentication |
| PostgreSQL | Latest | Production database |
| psycopg2-binary | 2.9.11 | PostgreSQL adapter |
| gunicorn | 25.3.0 | Production WSGI server |
| whitenoise | 6.12.0 | Static file serving |
| django-cors-headers | 4.9.0 | Cross-origin request handling |
| Render | Cloud | Deployment platform |

---

## API Endpoints (24 total)

Base URL: `https://smart-outlet-backend.onrender.com`

### Authentication & Profile
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/auth/register/ | No | Register a new user account |
| POST | /api/auth/login/ | No | Login and receive JWT tokens |
| POST | /api/token/refresh/ | No | Obtain a new access token |
| GET | /api/users/profile/ | Yes | Get logged in user profile |
| PATCH | /api/users/profile/ | Yes | Update user profile |

### Devices & Provisioning
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/devices/ | Yes | Get all devices with total count |
| POST | /api/devices/ | Yes | Register new device, returns claim code |
| DELETE | /api/devices/{id}/ | Yes | Permanently delete a device |
| PATCH | /api/devices/{id}/ | Yes | Rename a device |
| POST | /api/devices/{id}/control/ | Yes | Send ON/OFF command to device |
| GET | /api/devices/{id}/command/ | Yes | ESP32 polls for pending command |
| POST | /api/devices/{id}/regenerate-claim/ | Yes | Regenerate expired claim code |
| POST | /api/devices/claim/ | No | ESP32 exchanges claim code for device secret |
| POST | /api/devices/auth/ | No | ESP32 authenticates with device secret |

### Energy Monitoring
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | /api/energy/ | Yes | ESP32 submits sensor readings |
| GET | /api/energy/{id}/ | Yes | Energy history for one device |
| GET | /api/energy/history/ | Yes | Energy history for all devices |

### Safety Alerts
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/alerts/ | Yes | Get all safety alerts |
| POST | /api/alerts/report/ | Yes | ESP32 reports a detected fault |

### Scheduling
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/schedules/ | Yes | Get all schedules |
| POST | /api/schedules/ | Yes | Create a new schedule |
| DELETE | /api/schedules/{id}/ | Yes | Delete a specific schedule |
| GET | /api/schedules/device/{id}/ | Yes | Active schedules for one device |

### Activity History
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | /api/control-logs/ | Yes | Full ON/OFF activity history |

---

## Device Provisioning System

ESP32 devices never store real user account credentials. Instead:

1. User registers a device via the mobile app → backend generates a random 6-character claim code (15-minute expiry)
2. ESP32 submits that claim code to `/api/devices/claim/` → receives a permanent device ID and device secret
3. From then on, the ESP32 authenticates using `/api/devices/auth/` with its own device ID and secret — never the user's password
4. If the claim code expires before use, the app can request a new one via `/api/devices/{id}/regenerate-claim/`
5. Devices registered but never claimed within 15 minutes are automatically cleaned up

This means physical access to the ESP32 never exposes the user's actual login credentials.

---

## Scheduling Logic

Schedules support an optional start time, optional end time, and a repeat pattern: `daily`, `weekly`, `once`, or blank.

- **Daily**: compares only the time-of-day, ignoring the date, so it repeats every day automatically
- **Weekly**: compares both day-of-week and time-of-day
- **Once / no repeat**: compares the full datetime, so it only fires once

The ESP32 polls `/api/devices/{id}/command/` every 5 seconds; the backend evaluates active schedules on each poll and returns the correct ON/OFF state, logging the action with source `schedule` or `schedule_ended`.

---

## Safety Alert Design

Safety decisions are made **locally on the ESP32**, not by this backend. When the ESP32's own logic detects a dangerous condition (overload, overvoltage, etc.), it disconnects the relay immediately — without waiting for a server response — so protection still works if the internet is down. It then reports the event to `/api/alerts/report/`, and the backend's job is purely to store and expose that event via `/api/alerts/`.

---

## Database Structure

Six PostgreSQL tables, implemented as Django models:

- **Users** — extends Django's AbstractUser; adds phone and location fields
- **Devices** — name, location, firmware version, status, plus provisioning fields (`claim_code`, `claim_code_expires_at`, `is_claimed`, `device_secret_hash`)
- **EnergyRecords** — voltage, current, power, energy (kWh), timestamp
- **ControlLogs** — action, source (`mobile_app` / `schedule` / `schedule_ended`), timestamp
- **SafetyAlerts** — alert type, measured value, threshold value, action taken, timestamp
- **ApplianceSchedules** — optional start/end time, repeat pattern

---

## Security Features

- JWT authentication on all protected endpoints (access token: 30 minutes)
- Device claiming system so ESP32 hardware never stores user credentials
- Passwords hashed with Django's PBKDF2 (SHA-256), never stored in plaintext
- Rate limiting: 20 req/min unauthenticated, 100 req/min authenticated
- Per-user data isolation — a user can only see/control their own devices, energy data, and alerts
- Secrets (`SECRET_KEY`, `DATABASE_URL`, `DEBUG`) stored in Render's environment settings, never committed to Git
- HTTPS enforced through Render

> **Note:** CORS is currently configured with `CORS_ALLOW_ALL_ORIGINS = True` for development convenience. This should be restricted to the Flutter app's actual origin before production deployment.

---

## Project Structure

```
smart_outlet_backend/
├── smart_outlet/            # Django project root
│   ├── smart_outlet/        # Project configuration
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   └── api/                 # Main application
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── admin.py
├── build.sh                 # Render build script
├── requirements.txt
└── .env                      # Secret keys (not committed)
```

---

## How to Run Locally

```bash
# 1. Clone the repository
git clone https://github.com/Joan08-05/Smart-outlet-backend.git

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=your-postgres-url-here

# 5. Run migrations
python manage.py migrate

# 6. Start the server
python manage.py runserver
```

---

## Deployment

Deployed on Render as a Web Service connected to this repository's `main` branch. Every push triggers an automatic redeploy. `build.sh` installs dependencies, collects static files via whitenoise, and applies pending migrations before each deploy. The PostgreSQL database runs on Render's paid Starter tier for persistent storage without the 90-day expiry of the free tier.

---

## Known Limitations / In Progress

- SSL certificate verification on the ESP32 is currently disabled for development simplicity
- No email/phone verification at registration yet
- Daily/weekly scheduling has not yet been validated across multiple real-world days continuously
- Some Flutter analytics dashboard screens are still in progress
