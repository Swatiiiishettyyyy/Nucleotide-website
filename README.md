# Nucleotide-website_v11 - Master Documentation

## Overview

Nucleotide-website_v11 is a unified FastAPI application that provides a comprehensive backend API for a medical/healthcare platform. The application includes modules for authentication, user profiles, products, cart management, orders, addresses, members, consent management, and Google Meet integration for appointment booking.

**Version:** 3.0.0  
**Framework:** FastAPI (Python)  
**Database:** MySQL (via SQLAlchemy ORM)  
**Deployment:** Docker container on AWS App Runner  
**Port:** 8030 (hardcoded in dockerfile)

---

## Table of Contents

1. [Architecture](#architecture)
2. [Modules](#modules)
3. [Database](#database)
4. [API Endpoints](#api-endpoints)
5. [Environment Variables](#environment-variables)
6. [Deployment](#deployment)
7. [Development Setup](#development-setup)
8. [Google Meet Integration](#google-meet-integration)

---

## Architecture

### Technology Stack

- **Backend Framework:** FastAPI 0.104.0+
- **Database ORM:** SQLAlchemy 2.0+
- **Database:** MySQL (via PyMySQL)
- **Authentication:** JWT tokens (PyJWT)
- **Session Management:** Redis
- **Task Scheduling:** APScheduler
- **Payment Processing:** Razorpay
- **Migrations:** Alembic
- **Container:** Docker

### Project Structure

```
Nucleotide-website_v11/
├── main.py                      # Main FastAPI application entry point
├── database.py                  # Shared database connection and configuration
├── config.py                    # Application settings and configuration
├── deps.py                      # FastAPI dependencies (database sessions)
├── requirements.txt             # Python dependencies
├── dockerfile                   # Docker container configuration
├── alembic.ini                  # Alembic migration configuration
├── alembic_runner.py            # Migration runner script
├── create_all_tables.py          # Script to create all database tables
├── additional_env.txt           # Additional environment variables for AWS
│
├── Address_module/              # Address management module
├── Cart_module/                 # Shopping cart module
├── Category_module/             # Product categories module
├── Consent_module/              # User consent management
├── Login_module/                # Authentication and OTP module
│   ├── OTP/                     # OTP generation and verification
│   ├── Device/                   # Device session management
│   └── Utils/                    # Authentication utilities
├── Member_module/               # Member management module
├── Orders_module/               # Order processing and management
├── Product_module/              # Product catalog module
├── Profile_module/              # User profile management
│
└── gmeet_api/                   # Google Meet integration module
    ├── router.py                # Google Meet API endpoints
    ├── models.py                # Database models
    ├── schemas.py               # Pydantic request/response schemas
    ├── google_calendar_service.py  # Google Calendar API service
    ├── deps.py                  # Dependencies
    ├── utils.py                 # Utility functions
    └── create_tables.py         # Table creation script
```

---

## Modules

### 1. Authentication Module (`/auth`)
- **OTP Generation:** Send OTP to user's phone number
- **OTP Verification:** Verify OTP and generate JWT access token
- **Rate Limiting:** Prevents abuse with configurable limits
- **Session Management:** Tracks active user sessions

### 2. Profile Module (`/profile`)
- **User Profile:** Create, read, update user profiles
- **Profile Audit:** Tracks all profile changes

### 3. Product Module (`/products`)
- **Product Catalog:** List, search, and filter products
- **Product Details:** Get detailed product information
- **Category Filtering:** Filter products by category

### 4. Category Module (`/categories`)
- **Category Management:** List all product categories
- **Bootstrap Categories:** Seed default categories

### 5. Cart Module (`/cart`)
- **Cart Management:** Add, update, remove items from cart
- **Coupon System:** Apply discount coupons
- **Cart Audit:** Tracks cart changes

### 6. Address Module (`/address`)
- **Address Management:** CRUD operations for user addresses
- **Location Validation:** Validates pincodes and locations
- **Address Audit:** Tracks address changes

### 7. Consent Module (`/consent`)
- **User Consents:** Manage user consent records
- **Consent Products:** Link consents to products
- **Consent Tracking:** Audit trail for consent changes

### 8. Member Module (`/member`)
- **Member Management:** Add, update, remove family members
- **Member Profiles:** Store member information
- **Member Audit:** Tracks member changes

### 9. Orders Module (`/orders`)
- **Order Creation:** Create orders from cart
- **Order Processing:** Handle order status updates
- **Payment Integration:** Razorpay payment processing
- **Order Tracking:** Track order history and status

### 10. Audit Module (`/audit`)
- **Activity Logging:** Comprehensive audit trail
- **Query Interface:** Query audit logs with filters

### 11. Session Module (`/sessions`)
- **Device Sessions:** Manage device-based sessions
- **Session Cleanup:** Automatic cleanup of expired sessions
- **Session Tracking:** Track active sessions per user

### 12. Google Meet API (`/gmeet`)
- **Counsellor Onboarding:** Universal OAuth flow for counsellors
- **Calendar Integration:** Google Calendar availability checking
- **Appointment Booking:** Book Google Meet appointments
- **Appointment Management:** Cancel appointments

---

## Database

### Database Configuration

- **Connection:** MySQL via SQLAlchemy
- **Connection Pooling:** Configured with pool size, max overflow, timeout, and recycle settings
- **Migrations:** Alembic for schema versioning
- **Tables:** All tables use descriptive prefixes (e.g., `user_`, `order_`, `counsellor_gmeet_`)

### Key Tables

- `users` - User accounts and authentication
- `user_profiles` - User profile information
- `products` - Product catalog
- `categories` - Product categories
- `cart_items` - Shopping cart items
- `addresses` - User addresses
- `orders` - Order records
- `order_items` - Order line items
- `members` - Family members
- `user_consents` - User consent records
- `counsellor_gmeet_tokens` - Google OAuth tokens for counsellors
- `counsellor_gmeet_bookings` - Appointment bookings
- `counsellor_gmeet_activity_logs` - Activity logs
- `counsellor_gmeet_list` - Counsellor information

### Database Connection

The application uses a shared `database.py` module that:
- Loads `DATABASE_URL` from environment variables
- Configures connection pooling
- Provides `SessionLocal` for database sessions
- Handles both SQLite (development) and MySQL (production)

---

## API Endpoints

### Base URL
- **Local Development:** `http://localhost:8030`
- **Production:** `https://your-domain.com`

### Endpoint Groups

| Module | Base Path | Description |
|--------|-----------|-------------|
| Auth | `/auth` | Authentication and OTP |
| Profile | `/profile` | User profile management |
| Products | `/products` | Product catalog |
| Categories | `/categories` | Product categories |
| Cart | `/cart` | Shopping cart |
| Address | `/address` | Address management |
| Consent | `/consent` | Consent management |
| Member | `/member` | Member management |
| Orders | `/orders` | Order processing |
| Audit | `/audit` | Audit log queries |
| Sessions | `/sessions` | Session management |
| Google Meet | `/gmeet` | Appointment booking |

### API Documentation

- **Swagger UI:** `http://localhost:8030/docs`
- **ReDoc:** `http://localhost:8030/redoc`

### Health Check

```http
GET /health
```

Returns application health status.

---

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | MySQL connection string | `mysql+pymysql://user:pass@host:port/db` |
| `SECRET_KEY` | JWT secret key | Random string (min 32 chars) |
| `ALLOWED_ORIGINS` | CORS allowed origins | `*` or comma-separated list |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ALGORITHM` | JWT algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | Token expiry | `86400` (24 hours) |
| `OTP_EXPIRY_SECONDS` | OTP validity | `120` (2 minutes) |
| `OTP_MAX_REQUESTS_PER_HOUR` | Rate limit | `15` |
| `DB_POOL_SIZE` | Connection pool size | `10` |
| `DB_MAX_OVERFLOW` | Max overflow connections | `20` |
| `DB_POOL_TIMEOUT` | Pool timeout (seconds) | `30` |
| `DB_POOL_RECYCLE` | Connection recycle (seconds) | `3600` |

### Google Meet API Variables

See `additional_env.txt` for Google Meet API specific variables:
- `GOOGLE_OAUTH_REDIRECT_URI` - OAuth callback URL
- `FRONTEND_COUNSELLOR_SUCCESS_URL` - Success redirect (optional)
- `FRONTEND_COUNSELLOR_ERROR_URL` - Error redirect (optional)
- `ENVIRONMENT` - `development` or `production` (affects OAuth HTTP/HTTPS)

---

## Deployment

### Docker Deployment

The application is containerized and deployed on AWS App Runner.

#### Dockerfile

```dockerfile
FROM python:3.13.7-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8030
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8030"]
```

#### AWS App Runner Configuration

1. **Environment Variables:** Set all required variables in AWS App Runner configuration
2. **Port:** Fixed at 8030 (hardcoded in dockerfile)
3. **Health Check:** `/health` endpoint
4. **Credentials:** Place `credentials.json` in project root for Google Meet API

### Database Migrations

Migrations are handled automatically on startup via `alembic_runner.py`. For manual migrations:

```bash
python alembic_runner.py
```

### Table Creation

For fresh databases:

```bash
python create_all_tables.py
```

---

## Development Setup

### Prerequisites

- Python 3.13+
- MySQL database
- Redis (for session management)
- Google OAuth credentials (for Google Meet API)

### Installation

1. **Clone repository**
   ```bash
   cd Nucleotide-website_v11
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate  # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   - Copy `.env.example` to `.env` (if exists)
   - Set `DATABASE_URL` and `SECRET_KEY`
   - Configure other variables as needed

5. **Set up database**
   ```bash
   python create_all_tables.py
   python alembic_runner.py
   ```

6. **Run application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8030
   ```

### Google Meet API Setup

1. **Place credentials.json**
   - Download from Google Cloud Console
   - Place in project root directory

2. **Configure OAuth redirect URI**
   - Set `GOOGLE_OAUTH_REDIRECT_URI` in environment variables
   - Must match Google Cloud Console configuration

---

## Google Meet Integration

The Google Meet API module (`gmeet_api`) provides appointment booking functionality with Google Calendar integration.

### Features

- **Universal Counsellor Onboarding:** Self-service OAuth flow
- **Calendar Availability:** Check counsellor availability
- **Appointment Booking:** Book Google Meet appointments
- **Appointment Cancellation:** Cancel appointments
- **Activity Logging:** Comprehensive audit trail

### Database Tables

- `counsellor_gmeet_tokens` - OAuth tokens
- `counsellor_gmeet_bookings` - Appointments
- `counsellor_gmeet_activity_logs` - Activity logs
- `counsellor_gmeet_list` - Counsellor information

### Endpoints

See `FRONTEND_INTEGRATION_GUIDE.md` for detailed endpoint documentation.

### OAuth Flow

1. Counsellor visits `/gmeet/counsellor/connect`
2. Redirected to Google consent screen
3. Authorizes calendar access
4. Redirected back to `/gmeet/auth/callback`
5. System creates/updates counsellor record
6. Redirects to frontend success page (if configured)

---

## Security Considerations

### Authentication

- JWT tokens for API authentication
- Token expiry configured via `ACCESS_TOKEN_EXPIRE_SECONDS`
- OTP-based login with rate limiting

### CORS

- Configure `ALLOWED_ORIGINS` for production
- Default allows all origins (development only)

### Database

- Use connection pooling to prevent exhaustion
- Configure appropriate pool sizes for load
- Use SSL for production database connections

### OAuth

- Store OAuth tokens securely (encrypt in production)
- Use HTTPS in production (`ENVIRONMENT=production`)
- Validate redirect URIs

---

## Logging

### Application Logs

- Request/response logging via middleware
- Status codes and response times logged
- Error logging with stack traces

### Activity Logs

- Database-backed activity logs
- Tracks all API calls and changes
- Queryable via `/audit` endpoint

---

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   - Check `DATABASE_URL` format
   - Verify database is accessible
   - Check connection pool settings

2. **Import Errors**
   - Ensure all dependencies are installed
   - Check Python path configuration

3. **OAuth Errors**
   - Verify `credentials.json` exists
   - Check redirect URI matches Google Console
   - Ensure `ENVIRONMENT` is set correctly

4. **Port Conflicts**
   - Port 8030 is hardcoded in dockerfile
   - Do not set `PORT` environment variable

---

## Support

For detailed API endpoint documentation, see:
- **Frontend Integration Guide:** `FRONTEND_INTEGRATION_GUIDE.md`
- **API Documentation:** `http://localhost:8030/docs`

---

## Version History

- **v3.0.0** - Current version with Google Meet integration
- Includes all modules: Auth, Profile, Products, Cart, Orders, Address, Member, Consent, Sessions, Audit, Google Meet

---

## License

[Your License Here]

