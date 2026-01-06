"""Chat route - AI companion interface."""

from fastapi import APIRouter, Request, Form

from homo_ludens.recommender import Recommender

router = APIRouter(prefix="/chat")


@router.get("")
async def chat_page(request: Request):
    """Render the chat page."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    history = storage.load_conversation()

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "messages": history.messages,
        },
    )


@router.post("/send")
async def send_message(request: Request, message: str = Form(...)):
    """Send a message and get AI response."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    profile = storage.load_profile()
    history = storage.load_conversation()

    try:
        recommender = Recommender()
        response = recommender.chat(message, profile, history)

        # Save to history
        history.add_message("user", message)
        history.add_message("assistant", response)
        storage.save_conversation(history)

        return templates.TemplateResponse(
            "partials/chat_messages.html",
            {
                "request": request,
                "new_user_message": message,
                "new_assistant_message": response,
            },
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/chat_error.html",
            {
                "request": request,
                "error": str(e),
            },
        )


@router.post("/clear")
async def clear_chat(request: Request):
    """Clear chat history."""
    templates = request.app.state.templates
    storage = request.app.state.storage
    storage.clear_conversation()

    return templates.TemplateResponse(
        "partials/chat_cleared.html",
        {"request": request},
    )
