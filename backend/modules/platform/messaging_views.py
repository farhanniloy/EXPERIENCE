from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .messaging import (
    block_account,
    conversation_for_member,
    list_conversations,
    mark_conversation_read,
    send_message,
    serialize_message,
)
from .models import Message


class ConversationOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    booking_id = serializers.UUIDField()
    experience_title = serializers.CharField()
    other_party = serializers.CharField()
    unread_count = serializers.IntegerField()
    latest_message = serializers.CharField()
    updated_at = serializers.DateTimeField()


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=5000, trim_whitespace=True)


class MessageOutputSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    sender_id = serializers.UUIDField()
    is_mine = serializers.BooleanField()
    body = serializers.CharField()
    created_at = serializers.DateTimeField()
    read_at = serializers.DateTimeField(allow_null=True)
    moderation_status = serializers.CharField()


class BlockOutputSerializer(serializers.Serializer):
    blocked = serializers.BooleanField()


class ConversationReadOutputSerializer(serializers.Serializer):
    marked_read = serializers.IntegerField()


class ConversationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "messaging"

    @extend_schema(responses=ConversationOutputSerializer(many=True))
    def get(self, request):
        return Response(list_conversations(request.user))


class ConversationMessageListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "messaging"

    @extend_schema(responses=MessageOutputSerializer(many=True))
    def get(self, request, conversation_id):
        conversation = conversation_for_member(conversation_id, request.user)
        messages = list(
            conversation.messages.select_related("sender__along_account")
            .order_by("-created_at")[:100]
        )
        messages.reverse()
        return Response([serialize_message(message, request.user) for message in messages])

    @extend_schema(request=MessageCreateSerializer, responses={"201": MessageOutputSerializer})
    def post(self, request, conversation_id):
        conversation = conversation_for_member(conversation_id, request.user)
        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            message = send_message(
                conversation,
                request.user,
                serializer.validated_data["body"],
            )
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        message = Message.objects.select_related("sender__along_account").get(pk=message.pk)
        return Response(serialize_message(message, request.user), status=status.HTTP_201_CREATED)


class ConversationReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "messaging"

    @extend_schema(request=None, responses=ConversationReadOutputSerializer)
    def post(self, request, conversation_id):
        conversation = conversation_for_member(conversation_id, request.user)
        count = mark_conversation_read(conversation, request.user)
        return Response({"marked_read": count})


class BlockUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_scope = "messaging"

    @extend_schema(request=None, responses=BlockOutputSerializer)
    def post(self, request, user_id):
        try:
            block, _ = block_account(request.user, user_id)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        return Response({"blocked": True}, status=status.HTTP_201_CREATED)
