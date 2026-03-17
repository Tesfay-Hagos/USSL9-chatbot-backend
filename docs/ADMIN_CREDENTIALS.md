# Admin Board Credentials

## Default Seeded Credentials

On first startup, the backend seeds a default admin user into the database:

| Field   | Value                      |
|---------|----------------------------|
| **Email**    | `tesfay.hagos1421@gmail.com` |
| **Password** | `Test@admin123`              |

## Changing the Password

Use the **password reset** flow (email OTP) from the Admin board, or update the record directly in the database.

## Login

1. Open the Admin board (e.g. http://localhost:3001)
2. Enter **email** (not username) and password
3. Click **Sign In**

Credentials are validated against the `admin_users` table in the database.
