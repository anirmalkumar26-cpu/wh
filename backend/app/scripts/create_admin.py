from getpass import getpass
import sys

import backend.app.models
from backend.app.core.config import settings
from backend.app.core.database import Base, create_database
from backend.app.services.auth import AuthenticationError, create_staff


def main() -> int:
    email = input("Administrator email: ").strip()
    password = getpass("Password (12+ characters): ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        print("Passwords do not match.", file=sys.stderr)
        return 1
    engine, factory = create_database(settings.database_url)
    Base.metadata.create_all(engine)
    try:
        with factory() as session:
            user = create_staff(session, email, password, "administrator")
            print(f"Created administrator account: {user.email}")
    except AuthenticationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
