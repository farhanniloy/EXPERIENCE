import re

from django.db import transaction

from .models import Experience, HostProfile, ModerationQueueItem

_SOLICITATION_TERMS = re.compile(
    r"\b(?:escort(?:s|ing)?|sexual services?|sex work|intimate services?|"
    r"adult services?|dating|hook[- ]?up|prostitut(?:e|ion))\b",
    re.IGNORECASE,
)
_BANGLADESH_PHONE = re.compile(r"(?<!\w)(?:\+?88)?01[3-9]\d{8}(?!\w)")
_INTERNATIONAL_PHONE = re.compile(r"(?<!\w)\+[\d][\d ()-]{8,18}\d(?!\w)")
_SOCIAL_CONTACT = re.compile(
    r"\b(?:whats?app|telegram|instagram|facebook|signal|wechat|snapchat)\b|"
    r"(?:https?://)?(?:www\.)?(?:wa\.me|t\.me|instagram\.com|facebook\.com)/|"
    r"@[A-Za-z0-9_.]{3,}",
    re.IGNORECASE,
)


def flag_content(fields):
    flagged = {}
    for field, value in fields.items():
        if not isinstance(value, str) or not value.strip():
            continue
        reasons = []
        if _SOLICITATION_TERMS.search(value):
            reasons.append("prohibited_solicitation")
        if _BANGLADESH_PHONE.search(value) or _INTERNATIONAL_PHONE.search(value):
            reasons.append("phone_number")
        if _SOCIAL_CONTACT.search(value):
            reasons.append("off_platform_contact")
        if reasons:
            flagged[field] = reasons
    return flagged


def flag_host_profile(host):
    return flag_content(
        {
            "headline": host.headline,
            "biography": host.biography,
            "photos": " ".join(host.photos),
        }
    )


def flag_experience(experience):
    return flag_content(
        {
            "title": experience.title,
            "summary": experience.summary,
            "description": experience.description,
            "photos": " ".join(experience.media.values_list("object_key", flat=True)),
        }
    )


@transaction.atomic
def queue_host_application(host, flagged_fields):
    item, created = ModerationQueueItem.objects.get_or_create(
        host=host,
        experience=None,
        queue_type=ModerationQueueItem.QueueType.HOST_APPLICATION,
        status=ModerationQueueItem.Status.PENDING,
        defaults={"flagged_fields": flagged_fields},
    )
    if not created:
        item.flagged_fields = flagged_fields
        item.save(update_fields=["flagged_fields", "updated_at"])
    return item


@transaction.atomic
def queue_profile_content(host, flagged_fields):
    item, created = ModerationQueueItem.objects.get_or_create(
        host=host,
        experience=None,
        queue_type=ModerationQueueItem.QueueType.PROFILE_CONTENT,
        status=ModerationQueueItem.Status.PENDING,
        defaults={"flagged_fields": flagged_fields},
    )
    if not created:
        item.flagged_fields = flagged_fields
        item.save(update_fields=["flagged_fields", "updated_at"])
    return item


@transaction.atomic
def queue_listing_review(host, experience, first_listing, flagged_fields):
    queue_type = (
        ModerationQueueItem.QueueType.LISTING_CONTENT
        if flagged_fields
        else ModerationQueueItem.QueueType.FIRST_LISTING
    )
    item = ModerationQueueItem.objects.filter(
        experience=experience, status=ModerationQueueItem.Status.PENDING
    ).first()
    if not first_listing and not flagged_fields:
        if item is not None:
            item.status = ModerationQueueItem.Status.CLEARED
            item.save(update_fields=["status", "updated_at"])
        return None
    if item is None:
        return ModerationQueueItem.objects.create(
            host=host,
            experience=experience,
            queue_type=queue_type,
            flagged_fields=flagged_fields,
        )
    item.queue_type = queue_type
    item.flagged_fields = flagged_fields
    item.save(update_fields=["queue_type", "flagged_fields", "updated_at"])
    return item
