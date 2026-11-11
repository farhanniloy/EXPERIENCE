import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db.models import Q
from django.utils import timezone

from config.product import default_country_code, default_currency_code, default_time_zone

currency_code_validator = RegexValidator(r"^[A-Z]{3}$", "Use an uppercase ISO 4217 currency code.")


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class UserManager(models.Manager):
    @transaction.atomic
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = email.strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValueError("An authentication account already uses this email.")
        auth_user = get_user_model().objects.create_user(
            username=uuid.uuid4().hex, email=email, password=password
        )
        return self.create(auth_user=auth_user, email=email, **extra_fields)

    @transaction.atomic
    def create_superuser(self, email, password=None, **extra_fields):
        email = email.strip().lower()
        auth_user = get_user_model().objects.create_superuser(
            username=uuid.uuid4().hex, email=email, password=password
        )
        return self.create(auth_user=auth_user, email=email, **extra_fields)


class User(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        DELETED = "deleted", "Deleted"

    email = models.EmailField(unique=True, db_index=True)
    auth_user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="along_account"
    )
    display_name = models.CharField(max_length=120, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    country_code = models.CharField(max_length=2, default=default_country_code)
    timezone = models.CharField(max_length=64, default=default_time_zone)
    locale = models.CharField(max_length=12, default="en")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    is_email_verified = models.BooleanField(default=False)
    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class HostProfile(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="host_profile"
    )
    slug = models.SlugField(max_length=150, unique=True)
    headline = models.CharField(max_length=180, blank=True)
    biography = models.TextField(blank=True)
    image = models.CharField(max_length=500, default="/placeholder-host.svg")
    photos = models.JSONField(default=list, blank=True)
    city = models.CharField(max_length=100, db_index=True)
    country_code = models.CharField(max_length=2, default=default_country_code)
    languages = models.JSONField(default=list, blank=True)
    interests = models.JSONField(default=list, blank=True)
    service_radius_km = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    instant_booking_enabled = models.BooleanField(default=False)
    first_listing_approved = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    completed_bookings = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["status", "city"])]


class VerificationCheck(UUIDModel, TimestampedModel):
    class CheckType(models.TextChoices):
        AGE = "age", "Age"
        IDENTITY = "identity", "Identity"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="verification_checks"
    )
    provider = models.CharField(max_length=80)
    provider_reference = models.CharField(max_length=180, blank=True)
    check_type = models.CharField(max_length=12, choices=CheckType.choices)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    checked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "check_type", "status"])]


class Category(UUIDModel, TimestampedModel):
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="children")
    slug = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cover_image = models.CharField(max_length=500, blank=True)
    icon = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]


class Experience(UUIDModel, TimestampedModel):
    class PricingType(models.TextChoices):
        FIXED = "fixed", "Fixed"
        HOURLY = "hourly", "Hourly"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_REVIEW = "pending_review", "Pending review"
        PUBLISHED = "published", "Published"
        INACTIVE = "inactive", "Inactive"

    host = models.ForeignKey(HostProfile, on_delete=models.PROTECT, related_name="experiences")
    categories = models.ManyToManyField(Category, related_name="experiences", blank=True)
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField()
    summary = models.CharField(max_length=300, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(validators=[MinValueValidator(15)])
    min_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    max_duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    pricing_type = models.CharField(max_length=8, choices=PricingType.choices, default=PricingType.FIXED)
    price_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default=default_currency_code, validators=[currency_code_validator])
    instant_booking_enabled = models.BooleanField(default=False)
    cancellation_policy = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)

    class Meta:
        indexes = [
            models.Index(fields=["status", "price_minor"]),
            models.Index(fields=["host", "status"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price_minor__gte=0), name="experience_price_nonnegative"),
            models.CheckConstraint(condition=Q(duration_minutes__gt=0), name="experience_duration_positive"),
        ]


class ExperienceMedia(UUIDModel, TimestampedModel):
    class MediaType(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Video"

    experience = models.ForeignKey(Experience, on_delete=models.CASCADE, related_name="media")
    object_key = models.CharField(max_length=500)
    media_type = models.CharField(max_length=8, choices=MediaType.choices, default=MediaType.IMAGE)
    alt_text = models.CharField(max_length=200)
    sort_order = models.PositiveSmallIntegerField(default=0)


class ModerationQueueItem(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CLEARED = "cleared", "Cleared"

    class QueueType(models.TextChoices):
        HOST_APPLICATION = "host_application", "Host application"
        PROFILE_CONTENT = "profile_content", "Host profile content"
        FIRST_LISTING = "first_listing", "First listing"
        LISTING_CONTENT = "listing_content", "Listing content"

    host = models.ForeignKey(HostProfile, on_delete=models.CASCADE, related_name="moderation_items")
    experience = models.ForeignKey(
        Experience, on_delete=models.CASCADE, null=True, blank=True, related_name="moderation_items"
    )
    queue_type = models.CharField(max_length=24, choices=QueueType.choices)
    flagged_fields = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="moderation_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"])]


class AvailabilityRule(UUIDModel, TimestampedModel):
    host = models.ForeignKey(HostProfile, on_delete=models.CASCADE, related_name="availability_rules")
    weekday = models.PositiveSmallIntegerField(validators=[MinValueValidator(0), MaxValueValidator(6)])
    start_time = models.TimeField()
    end_time = models.TimeField()
    timezone = models.CharField(max_length=64, default=default_time_zone)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(end_time__gt=models.F("start_time")), name="availability_rule_positive_range"),
        ]
        indexes = [models.Index(fields=["host", "weekday", "is_active"])]


class AvailabilityException(UUIDModel, TimestampedModel):
    class ExceptionType(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNAVAILABLE = "unavailable", "Unavailable"

    host = models.ForeignKey(HostProfile, on_delete=models.CASCADE, related_name="availability_exceptions")
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    exception_type = models.CharField(max_length=12, choices=ExceptionType.choices)
    notes = models.CharField(max_length=250, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(end_at__gt=models.F("start_at")), name="availability_exception_positive_range"),
        ]
        indexes = [models.Index(fields=["host", "start_at", "end_at"])]


class Booking(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        AWAITING_PAYMENT = "awaiting_payment", "Awaiting payment"
        CONFIRMED = "confirmed", "Confirmed"
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"
        DISPUTED = "disputed", "Disputed"

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    host = models.ForeignKey(HostProfile, on_delete=models.PROTECT, related_name="bookings")
    experience = models.ForeignKey(Experience, on_delete=models.PROTECT, related_name="bookings")
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField()
    timezone = models.CharField(max_length=64, default=default_time_zone)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED, db_index=True)
    currency = models.CharField(max_length=3, default=default_currency_code, validators=[currency_code_validator])
    base_price_minor = models.PositiveBigIntegerField()
    fee_minor = models.PositiveBigIntegerField(default=0)
    tax_minor = models.PositiveBigIntegerField(default=0)
    total_minor = models.PositiveBigIntegerField()
    payment_deadline = models.DateTimeField(null=True, blank=True)
    public_venue_name = models.CharField(max_length=180, blank=True, default="")
    meeting_location_private = models.CharField(max_length=500, blank=True)
    customer_note = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["customer", "idempotency_key"], name="booking_customer_idempotency_unique"),
            models.CheckConstraint(condition=Q(end_at__gt=models.F("start_at")), name="booking_positive_time_range"),
            models.CheckConstraint(condition=Q(total_minor__gte=0), name="booking_total_nonnegative"),
        ]
        indexes = [
            models.Index(fields=["customer", "start_at"]),
            models.Index(fields=["host", "start_at", "status"]),
        ]


class BookingEvent(UUIDModel):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="booking_events")
    event_type = models.CharField(max_length=60)
    previous_state = models.CharField(max_length=20, blank=True)
    new_state = models.CharField(max_length=20, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)


class PaymentTransaction(UUIDModel, TimestampedModel):
    class TransactionType(models.TextChoices):
        AUTHORIZATION = "authorization", "Authorization"
        CAPTURE = "capture", "Capture"
        REFUND = "refund", "Refund"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FAILED = "failed", "Failed"
        AUTHORIZED = "authorized", "Authorized"
        CAPTURED = "captured", "Captured"
        REFUNDED = "refunded", "Refunded"
        PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=60)
    provider_reference = models.CharField(max_length=180, null=True, blank=True, unique=True)
    transaction_type = models.CharField(max_length=16, choices=TransactionType.choices)
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, validators=[currency_code_validator])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    idempotency_key = models.CharField(max_length=128, unique=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["booking", "created_at"])]
        constraints = [models.CheckConstraint(condition=Q(amount_minor__gte=0), name="payment_amount_nonnegative")]


class Payout(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ELIGIBLE = "eligible", "Eligible"
        PROCESSING = "processing", "Processing"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REVERSED = "reversed", "Reversed"

    host = models.ForeignKey(HostProfile, on_delete=models.PROTECT, related_name="payouts")
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="payouts")
    amount_minor = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, validators=[currency_code_validator])
    provider_reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(amount_minor__gte=0), name="payout_amount_nonnegative")]


class Conversation(UUIDModel, TimestampedModel):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="conversation")


class Message(UUIDModel):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="messages")
    body = models.TextField(max_length=5000)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    flagged = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["conversation", "created_at"])]


class Review(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        HIDDEN = "hidden", "Hidden"

    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, related_name="reviews")
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    host = models.ForeignKey(HostProfile, on_delete=models.PROTECT, related_name="reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    private_safety_feedback = models.TextField(blank=True, max_length=2000)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["booking", "reviewer"], name="review_booking_reviewer_unique"),
            models.CheckConstraint(condition=Q(rating__gte=1) & Q(rating__lte=5), name="review_rating_range"),
        ]
        indexes = [models.Index(fields=["host", "status", "created_at"])]


class SafetyReport(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        REVIEWING = "reviewing", "Reviewing"
        RESOLVED = "resolved", "Resolved"
        DISMISSED = "dismissed", "Dismissed"

    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_filed")
    reported = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reports_received")
    booking = models.ForeignKey(Booking, on_delete=models.PROTECT, null=True, blank=True, related_name="reports")
    reason = models.CharField(max_length=80)
    description = models.TextField(max_length=5000)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    assigned_admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="assigned_reports")


class Block(UUIDModel, TimestampedModel):
    blocker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_created")
    blocked = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blocks_received")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["blocker", "blocked"], name="block_user_pair_unique"),
            models.CheckConstraint(condition=~Q(blocker=models.F("blocked")), name="block_users_must_differ"),
        ]


class EventCollection(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    country_code = models.CharField(max_length=2, blank=True)
    city = models.CharField(max_length=100, blank=True)
    banner_image = models.CharField(max_length=500, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    experiences = models.ManyToManyField(Experience, through="CollectionExperience", related_name="collections")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__isnull=True) | Q(starts_at__isnull=True) | Q(ends_at__gt=models.F("starts_at")), name="collection_positive_period"),
        ]


class CollectionExperience(UUIDModel):
    collection = models.ForeignKey(EventCollection, on_delete=models.CASCADE)
    experience = models.ForeignKey(Experience, on_delete=models.CASCADE)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["collection", "experience"], name="collection_experience_unique"),
        ]


class AuditLog(UUIDModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="audit_logs")
    action = models.CharField(max_length=100)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False, db_index=True)


class SavedHost(UUIDModel, TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_hosts")
    host = models.ForeignKey(HostProfile, on_delete=models.CASCADE, related_name="saved_by")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "host"], name="saved_host_user_unique")]


class NotificationRecord(UUIDModel, TimestampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="notifications")
    notification_type = models.CharField(max_length=60)
    payload = models.JSONField(default=dict, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
