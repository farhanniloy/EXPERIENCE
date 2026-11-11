from django.contrib import admin

from .audit import record_admin_action
from .models import (
    AuditLog,
    AvailabilityException,
    AvailabilityRule,
    Booking,
    BookingEvent,
    Block,
    Category,
    CollectionExperience,
    Conversation,
    EventCollection,
    Experience,
    ExperienceMedia,
    HostProfile,
    Message,
    ModerationQueueItem,
    NotificationRecord,
    PaymentTransaction,
    PaymentWebhookEvent,
    Payout,
    Refund,
    Review,
    SafetyCheckIn,
    SafetyIncident,
    SafetyReport,
    User,
    VerificationCheck,
)


class AuditedModelAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        changed_fields = sorted(form.changed_data)
        super().save_model(request, obj, form, change)
        record_admin_action(
            request.user,
            f"{obj._meta.model_name}_{'updated' if change else 'created'}",
            obj,
            {"changed_fields": changed_fields},
        )

    def delete_model(self, request, obj):
        record_admin_action(request.user, f"{obj._meta.model_name}_deleted", obj)
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset.iterator():
            record_admin_action(request.user, f"{obj._meta.model_name}_deleted", obj)
        super().delete_queryset(request, queryset)


@admin.register(User)
class AccountAdmin(AuditedModelAdmin):
    list_display = ("email", "display_name", "status", "is_email_verified", "created_at")
    list_filter = ("status", "is_email_verified")
    search_fields = ("email", "display_name")
    readonly_fields = ("email", "auth_user", "birth_date", "created_at", "updated_at")

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        return fields if request.user.is_superuser else (*fields, "status")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.auth_user.is_active = obj.status == User.Status.ACTIVE
        obj.auth_user.save(update_fields=["is_active"])

    def has_add_permission(self, request):
        return False


@admin.register(HostProfile)
class HostProfileAdmin(AuditedModelAdmin):
    list_display = ("slug", "user", "city", "status", "verified", "created_at")
    list_filter = ("status", "verified", "city")
    search_fields = ("slug", "user__email", "user__along_account__display_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Experience)
class ExperienceAdmin(AuditedModelAdmin):
    list_display = ("title", "host", "status", "price_minor", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("title", "slug", "host__slug")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Category)
class CategoryAdmin(AuditedModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")


class CollectionExperienceInline(admin.TabularInline):
    model = CollectionExperience
    extra = 0


@admin.register(EventCollection)
class EventCollectionAdmin(AuditedModelAdmin):
    list_display = ("title", "slug", "city", "status", "starts_at", "ends_at")
    list_filter = ("status", "country_code", "city")
    search_fields = ("title", "slug", "city")
    inlines = (CollectionExperienceInline,)

    def save_related(self, request, form, formsets, change):
        related_changed = any(formset.has_changed() for formset in formsets)
        super().save_related(request, form, formsets, change)
        if related_changed:
            record_admin_action(
                request.user,
                "collection_experiences_updated",
                form.instance,
                {"experience_ids": [str(item) for item in form.instance.experiences.values_list("id", flat=True)]},
            )


@admin.register(ModerationQueueItem)
class ModerationQueueItemAdmin(AuditedModelAdmin):
    list_display = ("queue_type", "host", "experience", "status", "created_at")
    list_filter = ("queue_type", "status")
    readonly_fields = tuple(field.name for field in ModerationQueueItem._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(VerificationCheck)
class VerificationCheckAdmin(admin.ModelAdmin):
    list_display = ("user", "check_type", "status", "checked_at", "expires_at")
    list_filter = ("check_type", "status")
    search_fields = ("user__email",)
    readonly_fields = tuple(field.name for field in VerificationCheck._meta.fields)
    exclude = ("provider_reference", "metadata")


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "host", "status", "start_at", "total_minor", "currency")
    list_filter = ("status", "currency")
    search_fields = ("id", "customer__email", "host__slug")
    readonly_fields = tuple(field.name for field in Booking._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "booking", "provider", "transaction_type", "status", "amount_minor", "currency")
    list_filter = ("provider", "transaction_type", "status", "currency")
    readonly_fields = tuple(field.name for field in PaymentTransaction._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("booking", "host", "status", "amount_minor", "currency")
    list_filter = ("status", "currency")
    readonly_fields = tuple(field.name for field in Payout._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ("payment", "status", "amount_minor", "currency", "created_at")
    list_filter = ("status", "currency")
    readonly_fields = tuple(field.name for field in Refund._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PaymentWebhookEvent)
class PaymentWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider", "event_id", "result", "received_at", "processed_at")
    list_filter = ("provider", "result")
    readonly_fields = tuple(field.name for field in PaymentWebhookEvent._meta.fields)


@admin.register(SafetyReport)
class SafetyReportAdmin(AuditedModelAdmin):
    list_display = ("reason", "reporter", "reported", "status", "assigned_admin", "created_at")
    list_filter = ("status", "reason")
    readonly_fields = ("reporter", "reported", "booking", "review", "reason", "description", "created_at", "updated_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        previous_status = (
            SafetyReport.objects.filter(pk=obj.pk).values_list("status", flat=True).first()
            if change
            else None
        )
        super().save_model(request, obj, form, change)
        if previous_status != obj.status and hasattr(obj, "incident"):
            incident = obj.incident
            incident.status = obj.status
            incident.save(update_fields=["status", "updated_at"])
            record_admin_action(
                request.user,
                "safety_incident_updated",
                incident,
                {"report_id": str(obj.pk), "status": obj.status},
            )


@admin.register(SafetyIncident)
class SafetyIncidentAdmin(AuditedModelAdmin):
    list_display = ("booking", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in SafetyIncident._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SafetyCheckIn)
class SafetyCheckInAdmin(admin.ModelAdmin):
    list_display = ("booking", "user", "status", "updated_at")
    list_filter = ("status",)
    readonly_fields = tuple(field.name for field in SafetyCheckIn._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Review)
class ReviewAdmin(AuditedModelAdmin):
    list_display = ("host", "reviewer", "rating", "status", "created_at")
    list_filter = ("status", "rating")
    readonly_fields = (
        "booking",
        "reviewer",
        "host",
        "rating",
        "comment",
        "private_safety_feedback",
        "created_at",
        "updated_at",
    )

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "entity_type", "entity_id", "actor", "created_at")
    list_filter = ("action", "entity_type")
    search_fields = ("entity_id", "actor__email")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for model in (
    AvailabilityRule,
    AvailabilityException,
    ExperienceMedia,
    BookingEvent,
    Conversation,
    Message,
    Block,
    NotificationRecord,
):
    admin.site.register(model, AuditedModelAdmin)
