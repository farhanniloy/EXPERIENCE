from .models import AuditLog


def record_admin_action(actor, action, entity, metadata=None):
    AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        metadata=metadata or {},
    )
