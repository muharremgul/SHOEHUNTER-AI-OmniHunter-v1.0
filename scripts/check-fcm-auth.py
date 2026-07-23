import os
import secrets

import firebase_admin
from firebase_admin import messaging


def main() -> int:
    project_id = os.environ.get("FIREBASE_PROJECT_ID", "shophunter-radar")
    app = firebase_admin.initialize_app(options={"projectId": project_id})
    message = messaging.Message(
        fid=secrets.token_urlsafe(16),
        data={"kind": "authorization_check"},
    )
    try:
        messaging.send(message, app=app)
    except Exception as exc:
        response_type = type(exc).__name__
        permission_denied = response_type == "PermissionDeniedError"
        reached_fcm = response_type in {
            "InvalidArgumentError",
            "NotFoundError",
            "SenderIdMismatchError",
            "UnregisteredError",
        }
        print(f"response_type={response_type}")
        print(f"permission_denied={str(permission_denied).lower()}")
        print(f"authorized_request_reached_fcm={str(reached_fcm).lower()}")
        return 2 if permission_denied else (0 if reached_fcm else 1)
    print("unexpected_send_success=true")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
