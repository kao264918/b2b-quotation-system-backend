import enum

class UserStatus(str, enum.Enum):
    PENDING_PASSWORD = "pending_password"
    ACTIVE = "active"
    DISABLED = "disabled"

class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
