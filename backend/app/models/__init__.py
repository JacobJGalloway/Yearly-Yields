# Import all models here so Alembic's env.py sees them via Base.metadata
# when it calls `from app.models import Base`.
# Order matters for readability; SQLAlchemy resolves FK references by table name string
# so actual import order does not affect autogenerate correctness.

from app.models.base import Base, CreatedAtMixin, TimestampMixin, new_uuid  # noqa: F401
from app.models.user import User, UserRole, Permission, RolePermission  # noqa: F401
from app.models.field import GrowingArea, GrowingAreaPlot, GrowingAreaType, PlotType  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.crop import Crop, CropCycle, CropCycleStatus, YieldUnit  # noqa: F401
from app.models.sensor_reading import SensorReading, ReadingSource, AssessmentStatus  # noqa: F401
from app.models.historical_summary import HistoricalSummary  # noqa: F401
from app.models.alert import Alert, AlertType, AlertStatus  # noqa: F401
from app.models.yield_plan import YieldPlan, ConfidenceLevel  # noqa: F401
from app.models.invoice import CropRate, Invoice, InvoiceStatus  # noqa: F401
from app.models.weekly_sensor_summary import WeeklySensorSummary  # noqa: F401
from app.models.password_reset_token import PasswordResetToken  # noqa: F401
