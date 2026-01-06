"""Chat route - AI companion interface with multi-conversation support."""

import uuid
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse

from homo_ludens.models import Conversation
from homo_ludens.recommender import Recommender

router = APIRouter(prefix="/chat")

# Prefix for unsaved (new) conversations
NEW_CONV_PREFIX = "new-"


def is_new_conversation(conv_id: str) -> bool:
    """Check if this is an unsaved new conversation."""
    return conv_id.startswith(NEW_CONV_PREFIX)


def generate_new_conv_id() -> str:
    """Generate a temporary ID for a new unsaved conversation."""
    return f"{NEW_CONV_PREFIX}{uuid.uuid4()}"


def get_real_conv_id(conv_id: str) -> str:
    """Strip the new- prefix to get the real UUID."""
    if conv_id.startswith(NEW_CONV_PREFIX):
        return conv_id[len(NEW_CONV_PREFIX):]
    return conv_id


@router.get("")
async def chat_page(request: Request):
    """
    Render the chat page.
    Always creates a new conversation (not saved until first message).
    Also migrates legacy conversation.json if it exists.
    """
    storage = request.app.state.storage

    # Migrate legacy conversation if exists
    storage.migrate_legacy_conversation()

    # Generate a new conversation ID (not saved yet)
    new_conv_id = generate_new_conv_id()

    # Redirect to the new conversation
    return RedirectResponse(url=f"/chat/{new_conv_id}", status_code=302)


@router.get("/{conv_id}")
async def chat_conversation(request: Request, conv_id: str):
    """Render the chat page for a specific conversation."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    # Get all saved conversations for sidebar
    conversations = storage.list_conversations()

    if is_new_conversation(conv_id):
        # This is a new unsaved conversation
        real_id = get_real_conv_id(conv_id)
        conversation = Conversation(id=real_id, title="New Conversation")
    else:
        # Load existing conversation
        conversation = storage.get_conversation(conv_id)
        if not conversation:
            # Conversation not found, create new one
            new_conv_id = generate_new_conv_id()
            return RedirectResponse(url=f"/chat/{new_conv_id}", status_code=302)

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "conversations": conversations,
            "current_conversation": conversation,
            "current_conv_id": conv_id,  # Keep the full ID (with new- prefix if applicable)
            "messages": conversation.messages,
            "is_new_conversation": is_new_conversation(conv_id),
        },
    )


@router.post("/new")
async def new_conversation(request: Request):
    """Create a new conversation and redirect to it."""
    # Generate a new conversation ID (not saved yet)
    new_conv_id = generate_new_conv_id()

    # Return redirect for HTMX
    response = RedirectResponse(url=f"/chat/{new_conv_id}", status_code=302)
    response.headers["HX-Redirect"] = f"/chat/{new_conv_id}"
    return response


@router.post("/{conv_id}/send")
async def send_message(request: Request, conv_id: str, message: str = Form(...)):
    """Send a message and get AI response."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()

    # Check if this is a new unsaved conversation
    if is_new_conversation(conv_id):
        real_id = get_real_conv_id(conv_id)
        conversation = Conversation(id=real_id, title="New Conversation")
        is_first_message = True
    else:
        conversation = storage.get_conversation(conv_id)
        if not conversation:
            return templates.TemplateResponse(
                "partials/chat_error.html",
                {"request": request, "error": "Conversation not found"},
            )
        is_first_message = len(conversation.messages) == 0

    try:
        recommender = Recommender()

        # Convert Conversation to ConversationHistory-like object for the recommender
        from homo_ludens.models import ConversationHistory

        history = ConversationHistory(messages=conversation.messages)

        response = recommender.chat(message, profile, history)
        
        # Handle empty response
        if not response or not response.strip():
            response = "I'm sorry, I couldn't generate a response. Please try again."

        # Save to conversation
        conversation.add_message("user", message)
        conversation.add_message("assistant", response)
        storage.save_conversation_v2(conversation)

        # Check if this is the first exchange and title is still default
        should_generate_title = (
            len(conversation.messages) == 2
            and conversation.title == "New Conversation"
        )

        # Build response with redirect info if this was a new conversation
        response_data = {
            "request": request,
            "new_user_message": message,
            "new_assistant_message": response,
            "conversation": conversation,
            "should_generate_title": should_generate_title,
        }
        
        # If this was a new conversation, we need to redirect to the real URL
        if is_new_conversation(conv_id):
            response_data["redirect_to"] = f"/chat/{conversation.id}"

        return templates.TemplateResponse(
            "partials/chat_response.html",
            response_data,
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/chat_error.html",
            {"request": request, "error": str(e)},
        )


@router.post("/{conv_id}/rename")
async def rename_conversation(
    request: Request, conv_id: str, title: str = Form(...)
):
    """Rename a conversation."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    conversation = storage.rename_conversation(conv_id, title)
    if not conversation:
        return templates.TemplateResponse(
            "partials/chat_error.html",
            {"request": request, "error": "Conversation not found"},
        )

    # Return updated conversation item for sidebar
    conversations = storage.list_conversations()
    return templates.TemplateResponse(
        "partials/conversation_list.html",
        {
            "request": request,
            "conversations": conversations,
            "current_conversation_id": conv_id,
        },
    )


@router.delete("/{conv_id}")
async def delete_conversation(request: Request, conv_id: str):
    """Delete a conversation."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    deleted = storage.delete_conversation(conv_id)

    # Get remaining conversations
    conversations = storage.list_conversations()

    if conversations:
        # Redirect to most recent conversation
        next_conv = conversations[0]
        response = templates.TemplateResponse(
            "partials/conversation_deleted.html",
            {
                "request": request,
                "redirect_url": f"/chat/{next_conv.id}",
            },
        )
        response.headers["HX-Redirect"] = f"/chat/{next_conv.id}"
        return response
    else:
        # No conversations left, create new one
        new_conv = storage.create_conversation()
        response = templates.TemplateResponse(
            "partials/conversation_deleted.html",
            {
                "request": request,
                "redirect_url": f"/chat/{new_conv.id}",
            },
        )
        response.headers["HX-Redirect"] = f"/chat/{new_conv.id}"
        return response


@router.post("/{conv_id}/generate-title")
async def generate_title(request: Request, conv_id: str):
    """Generate an AI title for the conversation."""
    templates = request.app.state.templates
    storage = request.app.state.storage

    conversation = storage.get_conversation(conv_id)
    if not conversation or len(conversation.messages) < 2:
        return templates.TemplateResponse(
            "partials/conversation_title.html",
            {
                "request": request,
                "conversation": conversation or Conversation(id=conv_id),
                "is_current": True,
            },
        )

    try:
        recommender = Recommender()
        title = recommender.generate_title(conversation.messages)

        # Save the new title
        conversation.title = title
        storage.save_conversation_v2(conversation)

        # Return updated conversation list
        conversations = storage.list_conversations()
        return templates.TemplateResponse(
            "partials/conversation_list.html",
            {
                "request": request,
                "conversations": conversations,
                "current_conversation_id": conv_id,
            },
        )
    except Exception:
        # If title generation fails, just return current state
        conversations = storage.list_conversations()
        return templates.TemplateResponse(
            "partials/conversation_list.html",
            {
                "request": request,
                "conversations": conversations,
                "current_conversation_id": conv_id,
            },
        )


# Legacy route for compatibility
@router.post("/clear")
async def clear_chat(request: Request):
    """Clear chat history (legacy, redirects to new conversation)."""
    storage = request.app.state.storage
    conversation = storage.create_conversation()

    response = RedirectResponse(url=f"/chat/{conversation.id}", status_code=302)
    response.headers["HX-Redirect"] = f"/chat/{conversation.id}"
    return response
