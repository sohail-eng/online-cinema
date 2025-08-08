import secrets

from mailjet_rest import Client
from settings import settings

api_key = settings.MAILJET_API_KEY
api_secret = settings.MAILJET_API_SECRET_KEY

mailjet = Client(auth=(api_key, api_secret), version="v3.1")


def send_email(user_email: str, subject: str, html: str, user_name: str = "User") -> None:
    admin_email = settings.ADMIN_EMAIL
    admin_full_name = settings.ADMIN_FULL_NAME

    data = {
        "Messages": [
            {
                "From": {
                    "email": admin_email,
                    "Name": admin_full_name
                },
                "To": [
                    {
                        "email": user_email,
                        "Name": user_name
                    }
                ],
                "Subject": subject,
                "HTMLPart": html
            }
        ]
    }
    mailjet.send.create(data=data)


def generate_secret_code(length=32) -> str:
    return secrets.token_urlsafe(length)

