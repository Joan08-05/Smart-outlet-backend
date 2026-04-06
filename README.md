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
- Automatically detecting dangerous electrical conditions and creating safety alerts
- Managing user authentication securely using JWT tokens

---

## Tech Stack

| Technology | Purpose |
|---|---|
| Django 6.0 | Web framework |
| Django REST Framework | API development |
| PostgreSQL | Production database |
| JWT (SimpleJWT) | User authentication |
| Render | Cloud deployment |
| Python 3.14 | Programming language |

---

## API Endpoints

| Method | Endpoint | Description | Access |
|---|---|---|---|
| POST | /api/auth/register/ | Register a new user | Public |
| POST | /api/auth/login/ | Login and receive JWT tokens | Public |
| GET | /api/devices/ | Get all devices for logged in user | Authenticated |
| POST | /api/devices/ | Register a new device | Authenticated |
| POST | /api/devices/{id}/control/ | Send ON/OFF command to device | Authenticated |
| GET | /api/devices/{id}/command/ | ESP32 polls for pending commands | Authenticated |
| POST | /api/energy/ | ESP32 sends sensor readings | Authenticated |
| GET | /api/energy/{id}/ | Get energy history for a device | Authenticated |
| GET | /api/alerts/ | Get all safety alerts | Authenticated |

---

## Database Structure

The system uses 6 database tables:

- **Users** - Stores registered user details including name, email, hashed password and phone number
- **Devices** - Stores smart outlet device information including name, location, firmware version and status
- **Energy Records** - Stores real-time and historical sensor readings including voltage, current, power and energy in kWh
- **Control Logs** - Tracks every ON/OFF action performed, who did it and when
- **Safety Alerts** - Stores overload and overvoltage events including measured value and threshold exceeded
- **Appliance Schedules** - Manages scheduled device operations including start time, end time and repeat pattern

---

## Security Features

- JWT token authentication on all protected endpoints
- Password hashing using Django's built-in system - passwords are never stored as plain text
- Rate limiting - 20 requests per minute for unauthenticated users, 100 per minute for authenticated users
- Access tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Secret keys stored in .env file, never pushed to GitHub
- HTTPS enforced through Render deployment

---

## Safety Alert Logic

When the ESP32 sends sensor data, the backend automatically checks:

- **Overload** - if power exceeds 3000W (maximum load defined in project scope)
- **Overvoltage** - if voltage exceeds 260V (above Tanzanian standard of 230V AC)

If either threshold is exceeded, a safety alert is automatically created in the database and the user is notified through the mobile application.

---

## ESP32 Communication

The ESP32 microcontroller communicates with the backend through polling:

1. Mobile app sends ON/OFF command to `/api/devices/{id}/control/`
2. Backend stores the command in the database
3. ESP32 polls `/api/devices/{id}/command/` every few seconds
4. ESP32 reads the current status and executes it physically

This polling approach is used because the ESP32 is behind a home Wi-Fi router and has no public IP address, so the backend cannot reach it directly. Instead the ESP32 always initiates the connection.

---

## Project Structure
```
smart_outlet_backend/
├── smart_outlet/          # Django project root
│   ├── smart_outlet/      # Project configuration
│   │   ├── settings.py    # Project settings
│   │   └── urls.py        # Main URL routing
│   └── api/               # Main application
│       ├── models.py      # Database models
│       ├── serializers.py # Data serializers
│       ├── views.py       # API logic
│       ├── urls.py        # API URL routing
│       └── admin.py       # Admin panel setup
├── requirements.txt       # Project dependencies
└── .env                   # Secret keys (not on GitHub)
```

---

## How to Run Locally

1. Clone the repository
git clone https://github.com/Joan08-05/Smart-outlet-backend.git

2. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate

3. Install dependencies
pip install -r requirements.txt

4. Create .env file with your secret key
SECRET_KEY=your-secret-key-here
DEBUG=True

5. Run migrations
python manage.py migrate

6. Start the server
python manage.py runserver