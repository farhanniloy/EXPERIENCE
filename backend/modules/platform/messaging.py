from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import (
    Block,
    Conversation,
    Message,
    ModerationQueueItem,
    User,
)
from .moderation import flag_content
from .notifications import enqueue_email


def conversation_for_member(conversation_id, auth_user):
    return get_object_or_404(
        Conversation.objects.select_related(
            "booking__customer__along_account",
            "booking__host__user__along_account",
            "booking__experience",
        ).filter(
            Q(booking__customer=auth_user) | Q(booking__host__user=auth_user)
        ),
        pk=conversation_id,
    )


def is_blocked_between(first_user_id, second_user_id):
    return Block.objects.filter(
        Q(blocker_id=first_user_id, blocked_id=second_user_id)
        | Q(blocker_id=second_user_id, blocked_id=first_user_id)
    ).exists()


def serialize_message(message, viewer):
    visible_to_viewer = (
        message.moderation_status == Message.ModerationStatus.VISIBLE
        or (
            message.moderation_status == Message.ModerationStatus.PENDING
            and message.sender_id == viewer.pk
        )
    )
    return {
        "id": str(message.pk),
        "sender_id": str(message.sender.along_account.id),
        "is_mine": message.sender_id == viewer.pk,
        "body": message.body if visible_to_viewer else "",
        "created_at": message.created_at,
        "read_at": message.read_at,
        "moderation_status": message.moderation_status,
    }


@transaction.atomic
def send_message(conversation, sender, body):
    body = body.strip()
    if not body:
        raise ValidationError("Message cannot be empty.")
    if len(body) > 5000:
        raise ValidationError("Message must be 5000 characters or fewer.")
    booking = conversation.booking
    if sender.pk == booking.customer_id:
        recipient = booking.host.user
    elif sender.pk == booking.host.user_id:
        recipient = booking.customer
    else:
        raise ValidationError("Only booking participants can send messages.")
    if User.objects.filter(
        auth_user_id__in=[sender.pk, recipient.pk],
        status=User.Status.ACTIVE,
    ).count() != 2:
        raise ValidationError("Messaging is unavailable for an inactive account.")
    if is_blocked_between(sender.pk, recipient.pk):
        raise ValidationError("Messaging is unavailable because one participant has blocked the other.")

    flags = flag_content({"body": body})
    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=body,
        flagged=bool(flags),
        moderation_status=Message.ModerationStatus.PENDING if flags else Message.ModerationStatus.VISIBLE,
    )
    conversation.save(update_fields=["updated_at"])
    if flags:
        ModerationQueueItem.objects.create(
            host=booking.host,
            experience=booking.experience,
            message=message,
            queue_type=ModerationQueueItem.QueueType.MESSAGE_CONTENT,
            flagged_fields=flags,
        )
    else:
        enqueue_email(
            recipient,
            "new_message",
            "message",
            message.pk,
            {"title": booking.snapshot.get("title", booking.experience.title)},
        )
    return message


def list_conversations(auth_user):
    conversations = (
        Conversation.objects.filter(
            Q(booking__customer=auth_user) | Q(booking__host__user=auth_user)
        )
        .select_related("booking__experience", "booking__customer__along_account", "booking__host__user__along_account")
        .prefetch_related(Prefetch(
            "messages",
            queryset=Message.objects.filter(
                moderation_status=Message.ModerationStatus.VISIBLE
            ).order_by("-created_at")[:1],
            to_attr="latest_messages",
        ))
        .annotate(
            unread_count=Count(
                "messages",
                filter=(
                    ~Q(messages__sender=auth_user)
                    & Q(messages__read_at__isnull=True)
                    & Q(messages__moderation_status=Message.ModerationStatus.VISIBLE)
                ),
            )
        )
        .order_by("-updated_at")[:100]
    )
    results = []
    for conversation in conversations:
        latest = conversation.latest_messages[0] if conversation.latest_messages else None
        booking = conversation.booking
        if booking.customer_id == auth_user.pk:
            other_party = booking.host.user.along_account.display_name
        else:
            other_party = booking.customer.along_account.display_name
        results.append({
            "id": str(conversation.pk),
            "booking_id": str(booking.pk),
            "experience_title": booking.snapshot.get("title", booking.experience.title),
            "other_party": other_party,
            "unread_count": conversation.unread_count,
            "latest_message": latest.body if latest else "",
            "updated_at": latest.created_at if latest else conversation.updated_at,
        })
    return results


@transaction.atomic
def mark_conversation_read(conversation, auth_user):
    return Message.objects.filter(
        conversation=conversation,
        read_at__isnull=True,
        moderation_status=Message.ModerationStatus.VISIBLE,
    ).exclude(sender=auth_user).update(read_at=timezone.now())


@transaction.atomic
def block_account(blocker, account_id):
    account = get_object_or_404(User.objects.select_related("auth_user"), pk=account_id)
    if account.auth_user_id == blocker.pk:
        raise ValidationError("You cannot block your own account.")
    if account.status != User.Status.ACTIVE:
        raise ValidationError("This account is unavailable.")
    block, created = Block.objects.get_or_create(blocker=blocker, blocked=account.auth_user)
    return block, created
