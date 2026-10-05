import os
import time

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash

from dotenv import load_dotenv

from google import genai
from google.genai import types

from .models import (
    Goal,
    StudyPlan,
    Task,
    ChatConversation,
    ChatMessage
)


load_dotenv()


# =========================================================
# HOME
# =========================================================

def home(request):
    return render(request, "home.html")


# =========================================================
# NEW CHAT
# =========================================================

@login_required
def new_chat(request):

    conversation = ChatConversation.objects.create(
        user=request.user,
        title="New Chat"
    )

    return redirect(
        "chat",
        conversation_id=conversation.id
    )


# =========================================================
# DELETE CHAT
# =========================================================

@login_required
def delete_chat(request, conversation_id):

    conversation = get_object_or_404(
        ChatConversation,
        id=conversation_id,
        user=request.user
    )

    conversation.delete()

    return redirect("chat_home")


# =========================================================
# CLEAR CHAT
# =========================================================

@login_required
def clear_chat(request, conversation_id):

    conversation = get_object_or_404(
        ChatConversation,
        id=conversation_id,
        user=request.user
    )

    ChatMessage.objects.filter(
        conversation=conversation
    ).delete()

    conversation.title = "New Chat"
    conversation.save()

    return redirect(
        "chat",
        conversation_id=conversation.id
    )


# =========================================================
# AI CHAT
# =========================================================

@login_required
def chat(request, conversation_id=None):

    # -----------------------------------------------------
    # GET CONVERSATION
    # -----------------------------------------------------

    if conversation_id:

        conversation = get_object_or_404(
            ChatConversation,
            id=conversation_id,
            user=request.user
        )

    else:

        conversation = (
            ChatConversation.objects
            .filter(user=request.user)
            .order_by("-created_at")
            .first()
        )

        if not conversation:

            conversation = ChatConversation.objects.create(
                user=request.user,
                title="New Chat"
            )

        return redirect(
            "chat",
            conversation_id=conversation.id
        )

    # -----------------------------------------------------
    # POST MESSAGE
    # -----------------------------------------------------

    if request.method == "POST":

        message = request.POST.get(
            "message",
            ""
        ).strip()

        print(
            "CHAT MESSAGE RECEIVED:",
            repr(message)
        )

        if message:

            # -------------------------------------------------
            # USER GOALS
            # -------------------------------------------------

            goals = Goal.objects.filter(
                user=request.user
            )[:10]

            goal_text = "\n".join(
                f"- {goal.title}"
                for goal in goals
            )

            if not goal_text:
                goal_text = "No goals added yet."

            # -------------------------------------------------
            # STUDY PLANS
            # -------------------------------------------------

            study_plans = StudyPlan.objects.filter(
                user=request.user
            )[:10]

            study_text = "\n".join(
                f"- {plan.subject}: {plan.hours} hours"
                for plan in study_plans
            )

            if not study_text:
                study_text = "No study plans added yet."

            # -------------------------------------------------
            # TASKS
            # -------------------------------------------------

            tasks = (
                Task.objects
                .filter(user=request.user)
                .order_by(
                    "-completed",
                    "-priority",
                    "-created_at"
                )[:10]
            )

            task_text = "\n".join(
                f"- {task.title} | "
                f"Priority: {task.priority} | "
                f"Completed: {task.completed}"
                for task in tasks
            )

            if not task_text:
                task_text = "No tasks added yet."

            # -------------------------------------------------
            # PREVIOUS CHAT
            # -------------------------------------------------

            previous_messages = (
                ChatMessage.objects
                .filter(
                    conversation=conversation
                )
                .order_by("-created_at")[:10]
            )

            previous_messages = reversed(
                list(previous_messages)
            )

            history_text = ""

            for old_message in previous_messages:

                role = (
                    "User"
                    if old_message.role == "user"
                    else "LifePilot AI"
                )

                content = old_message.content[:2000]

                history_text += (
                    f"{role}: {content}\n"
                )

            if not history_text:
                history_text = "No previous conversation."

            # -------------------------------------------------
            # SYSTEM INSTRUCTION
            # -------------------------------------------------

            system_instruction = """
You are LifePilot AI — a smart, friendly and practical personal AI assistant.

Your job is to understand exactly what the user needs and provide the
most useful answer with the minimum necessary information.

IMPORTANT:
Quality matters more than length.

ANSWER STYLE:

1. Answer the exact question first.

2. Keep answers concise and useful.

3. Very simple question:
   Give 2–4 short lines.

4. Normal question:
   Give 3–6 useful points.

5. Detailed question:
   Give a structured explanation.

6. Step-by-step request:
   Use numbered steps.

7. Use short sentences.

8. Avoid long paragraphs.

9. Do not repeat the same idea.

10. Do not repeat the user's question.

11. Do not start with:
   "Sure!", "Of course!", "Certainly!", "Absolutely!"

12. Do not unnecessarily end with:
   "Let me know if you want..."

FORMATTING:

• Use simple bullet points.
• Use numbered lists for steps.
• Use short headings only when useful.
• Do not use *, **, ## or ###.
• Do not create huge blocks of text.
• Use very few emojis.

PROGRAMMING QUESTIONS:

Give:
1. Direct solution
2. Required code or steps
3. Short explanation

STUDY AND CAREER:

Give practical and actionable guidance.

Prefer:
• What to learn
• What to do next
• How to practice
• Expected outcome

CURRENT INFORMATION:

Do not guess.
If current information is required, clearly say when information
cannot be verified.

ACCURACY:

Never invent facts.
Never pretend to perform an action.
If something is uncertain, say so briefly.

PERSONALIZATION:

Use the user's goals, study plans and tasks when relevant.

TONE:

Friendly.
Smart.
Practical.
Natural.
Encouraging.

FINAL RULE:

Understand what the user actually wants and answer that directly.
"""


            # -------------------------------------------------
            # USER CONTEXT
            # -------------------------------------------------

            conversation_text = f"""
USER GOALS:
{goal_text}

USER STUDY PLANS:
{study_text}

USER TASKS:
{task_text}

RECENT CONVERSATION:
{history_text}

CURRENT USER QUESTION:
{message}

Answer the current question directly.
Do not unnecessarily repeat previous answers.
"""


            # =================================================
            # GEMINI API
            # =================================================

            try:

                # -------------------------------------------------
                # GET API KEY
                # -------------------------------------------------

                api_key = os.getenv(
                    "GEMINI_API_KEY"
                )

                if not api_key:

                    raise ValueError(
                        "GEMINI_API_KEY is missing."
                    )


                # -------------------------------------------------
                # CREATE GEMINI CLIENT
                # -------------------------------------------------

                client = genai.Client(
                    api_key=api_key
                )


                # -------------------------------------------------
                # GEMINI CONFIG
                # -------------------------------------------------

                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=1000
                )


                # -------------------------------------------------
                # MODELS
                # -------------------------------------------------

                models_to_try = [
                    "gemini-3.5-flash-lite",
                    "gemini-3.5-flash",
                    "gemini-3.1-flash-lite",
                ]


                response = None


                # -------------------------------------------------
                # TRY GEMINI MODELS
                # -------------------------------------------------

                for model_name in models_to_try:

                    model_response = None

                    for attempt in range(2):

                        try:

                            print(
                                "Trying Gemini model:",
                                model_name,
                                "Attempt:",
                                attempt + 1
                            )


                            model_response = (
                                client.models.generate_content(
                                    model=model_name,
                                    contents=conversation_text,
                                    config=config
                                )
                            )


                            if (
                                model_response
                                and model_response.text
                            ):

                                response = model_response
                                break


                        except Exception as e:

                            error_text = str(e).lower()

                            print(
                                "Gemini attempt error:",
                                repr(e)
                            )


                            # -------------------------------------
                            # DAILY QUOTA
                            # -------------------------------------

                            if (
                                "quota_exceeded"
                                in error_text
                            ):

                                break


                            # -------------------------------------
                            # TRANSIENT ERROR
                            # -------------------------------------

                            retryable = (
                                "503" in error_text
                                or
                                "service_unavailable"
                                in error_text
                                or
                                "rate_limit_exceeded"
                                in error_text
                                or
                                (
                                    "429" in error_text
                                    and
                                    "quota_exceeded"
                                    not in error_text
                                )
                            )


                            if retryable:

                                if attempt == 0:

                                    time.sleep(2)

                                    continue

                                break


                            # -------------------------------------
                            # OTHER ERROR
                            # -------------------------------------

                            raise


                    if response and response.text:

                        break


                # -------------------------------------------------
                # CHECK RESPONSE
                # -------------------------------------------------

                if not response or not response.text:

                    raise Exception(
                        "AI response could not be generated."
                    )


                ai_response = response.text.strip()


                # -------------------------------------------------
                # SAVE USER MESSAGE
                # -------------------------------------------------

                ChatMessage.objects.create(
                    conversation=conversation,
                    role="user",
                    content=message
                )


                # -------------------------------------------------
                # SAVE AI RESPONSE
                # -------------------------------------------------

                ChatMessage.objects.create(
                    conversation=conversation,
                    role="assistant",
                    content=ai_response
                )


                # -------------------------------------------------
                # CHAT TITLE
                # -------------------------------------------------

                if conversation.title == "New Chat":

                    conversation.title = message[:40]
                    conversation.save()


                # -------------------------------------------------
                # REDIRECT
                # -------------------------------------------------

                return redirect(
                    "chat",
                    conversation_id=conversation.id
                )


            # =====================================================
            # ERROR HANDLING
            # =====================================================

            except Exception as e:

                print(
                    "GEMINI AI ERROR:",
                    repr(e)
                )


                # -------------------------------------------------
                # USER-FACING MESSAGE
                # -------------------------------------------------
                # Technical error details are NOT shown in chat.

                friendly_message = (
                    "I couldn't generate the answer right now. "
                    "Please try again."
                )


                ChatMessage.objects.create(
                    conversation=conversation,
                    role="user",
                    content=message
                )


                ChatMessage.objects.create(
                    conversation=conversation,
                    role="assistant",
                    content=friendly_message
                )


                return redirect(
                    "chat",
                    conversation_id=conversation.id
                )


    # =========================================================
    # CHAT LIST
    # =========================================================

    conversations = (
        ChatConversation.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )


    # =========================================================
    # CURRENT CHAT MESSAGES
    # =========================================================

    chat_messages = (
        ChatMessage.objects
        .filter(
            conversation=conversation
        )
        .order_by("created_at")
    )


    return render(
        request,
        "chat.html",
        {
            "conversation": conversation,
            "conversations": conversations,
            "chat_messages": chat_messages,
        }
    )


# =========================================================
# GOALS
# =========================================================

@login_required
def goals(request):

    if request.method == "POST":

        title = request.POST.get(
            "title",
            ""
        ).strip()

        if title:

            Goal.objects.create(
                user=request.user,
                title=title
            )

        return redirect("goals")


    user_goals = (
        Goal.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )


    return render(
        request,
        "goals.html",
        {
            "goals": user_goals
        }
    )


# =========================================================
# DELETE GOAL
# =========================================================

@login_required
def delete_goal(request, goal_id):

    goal = get_object_or_404(
        Goal,
        id=goal_id,
        user=request.user
    )

    goal.delete()

    return redirect("goals")


# =========================================================
# STUDY
# =========================================================

@login_required
def study(request):

    if request.method == "POST":

        subject = request.POST.get(
            "subject",
            ""
        ).strip()

        hours = request.POST.get(
            "hours",
            ""
        ).strip()


        if subject and hours:

            try:

                hours_value = float(hours)

                if hours_value > 0:

                    StudyPlan.objects.create(
                        user=request.user,
                        subject=subject,
                        hours=hours_value
                    )

            except (ValueError, TypeError):

                pass


        return redirect("study")


    plans = (
        StudyPlan.objects
        .filter(user=request.user)
        .order_by("-created_at")
    )


    return render(
        request,
        "study.html",
        {
            "plans": plans
        }
    )


# =========================================================
# DELETE STUDY PLAN
# =========================================================

@login_required
def delete_study_plan(request, plan_id):

    plan = get_object_or_404(
        StudyPlan,
        id=plan_id,
        user=request.user
    )

    plan.delete()

    return redirect("study")


# =========================================================
# CAREER
# =========================================================

@login_required
def career(request):
    career = None
    result = None

    if request.method == "POST":
        career = request.POST.get("career", "").strip()

        if career:
            try:
                api_key = os.getenv("GEMINI_API_KEY")

                client = genai.Client(api_key=api_key)

                prompt = f"""
You are LifePilot AI Career Assistant.

The user's career interest is: {career}

Give practical career guidance in a clear and concise format.

Include:
1. Career overview
2. Skills to learn
3. Important tools/technologies
4. Project ideas
5. Learning roadmap
6. Interview preparation
7. A simple next-step plan

Keep the answer useful for a college student.
Do not make unrealistic salary promises.
"""

                response = client.models.generate_content(
                    model="gemini-3.5-flash-lite",
                    contents=prompt
                )

                result = response.text.strip()

            except Exception as e:
                print("CAREER AI ERROR:", e)
                result = (
                    "AI career guidance is temporarily unavailable. "
                    "Please try again."
                )

    return render(
        request,
        "career.html",
        {
            "career": career,
            "result": result,
        }
    )

# =========================================================
# DASHBOARD
# =========================================================

@login_required
def dashboard(request):

    goals_count = Goal.objects.filter(
        user=request.user
    ).count()

    study_count = StudyPlan.objects.filter(
        user=request.user
    ).count()

    tasks = Task.objects.filter(
        user=request.user
    )

    tasks_count = tasks.count()

    completed_tasks = tasks.filter(
        completed=True
    ).count()

    pending_tasks = tasks.filter(
        completed=False
    ).count()

    if tasks_count > 0:

        progress = int(
            (
                completed_tasks
                / tasks_count
            ) * 100
        )

    else:

        progress = 0

    pending_task_list = (
        tasks
        .filter(completed=False)
        .order_by(
            "-priority",
            "-created_at"
        )[:5]
    )

    # -----------------------------
    # Fallback Suggestions
    # -----------------------------

    suggestions = []

    if pending_tasks > 0:
        suggestions.append(
            "Complete one pending task today before starting a new task."
        )

    if study_count == 0:
        suggestions.append(
            "Add your first study plan and start tracking your learning."
        )
    else:
        suggestions.append(
            "Review your study plan and maintain a consistent daily schedule."
        )

    if goals_count == 0:
        suggestions.append(
            "Set a clear goal so LifePilot AI can help you track your progress."
        )
    else:
        suggestions.append(
            "Review your goals and work on one important goal today."
        )

    if completed_tasks > 0:
        suggestions.append(
            f"You have completed {completed_tasks} task(s). Keep the progress going!"
        )

    # -----------------------------
    # Gemini Personalized Suggestions
    # -----------------------------

    try:

        user_goals = list(
            Goal.objects
            .filter(user=request.user)
            .values_list("title", flat=True)[:5]
        )

        user_study = list(
            StudyPlan.objects
            .filter(user=request.user)
            .values("subject", "hours")[:5]
        )

        user_tasks = list(
            tasks
            .filter(completed=False)
            .values_list("title", flat=True)[:5]
        )

        prompt = f"""
You are LifePilot AI, a personal productivity assistant.

Create 3 short and practical daily suggestions for this user.

User Goals:
{user_goals}

Study Plans:
{user_study}

Pending Tasks:
{user_tasks}

Completed Tasks:
{completed_tasks}

Total Tasks:
{tasks_count}

Progress:
{progress}%

Rules:
- Give exactly 3 suggestions.
- Keep each suggestion short.
- Make them personalized using the user's actual goals, study plans and tasks.
- Focus on practical actions for today.
- Do not mention that you are an AI.
- Do not use markdown symbols.
- Return only the 3 suggestions, one per line.
"""

        api_key = os.getenv("GEMINI_API_KEY")

        if api_key:

            client = genai.Client(
                api_key=api_key
            )

            response = client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=prompt
            )

            if response and response.text:

                ai_lines = [
                    line.strip()
                    for line in response.text.splitlines()
                    if line.strip()
                ]

                if ai_lines:

                    suggestions = ai_lines[:3]

    except Exception as e:

        print(
            "DASHBOARD AI SUGGESTIONS ERROR:",
            e
        )

    return render(
        request,
        "dashboard.html",
        {
            "goals_count": goals_count,
            "study_count": study_count,
            "tasks_count": tasks_count,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "progress": progress,
            "pending_task_list": pending_task_list,
            "ai_suggestions": suggestions,
        }
    )
# =========================================================
# LOGIN
# =========================================================

def login_view(request):

    error = None


    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )


        user = authenticate(
            request,
            username=username,
            password=password
        )


        if user is not None:

            login(
                request,
                user
            )

            return redirect("dashboard")


        error = "Invalid username or password."


    return render(
        request,
        "login.html",
        {
            "error": error
        }
    )


# =========================================================
# REGISTER
# =========================================================

def register(request):

    error = None


    if request.method == "POST":

        username = request.POST.get(
            "username",
            ""
        ).strip()

        password = request.POST.get(
            "password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )


        if not username:

            error = "Username is required."


        elif not password:

            error = "Password is required."


        elif password != confirm_password:

            error = "Passwords do not match."


        elif len(password) < 6:

            error = "Password must be at least 6 characters."


        elif User.objects.filter(
            username=username
        ).exists():

            error = "Username already exists."


        else:

            user = User.objects.create_user(
                username=username,
                password=password
            )

            login(
                request,
                user
            )

            return redirect("dashboard")


    return render(
        request,
        "register.html",
        {
            "error": error
        }
    )


# =========================================================
# LOGOUT
# =========================================================

@login_required
def logout_view(request):

    if request.method == "POST":

        logout(request)

        return redirect("login")


    return render(
        request,
        "logout_confirm.html"
    )


# =========================================================
# TASKS
# =========================================================

@login_required
def tasks(request):

    if request.method == "POST":

        title = request.POST.get(
            "title",
            ""
        ).strip()

        priority = request.POST.get(
            "priority",
            "medium"
        ).strip().lower()


        if priority not in [
            "high",
            "medium",
            "low"
        ]:

            priority = "medium"


        if title:

            Task.objects.create(
                user=request.user,
                title=title,
                priority=priority
            )


        return redirect("tasks")


    user_tasks = (
        Task.objects
        .filter(user=request.user)
        .order_by(
            "-completed",
            "-priority",
            "-created_at"
        )
    )


    return render(
        request,
        "tasks.html",
        {
            "tasks": user_tasks
        }
    )


# =========================================================
# TOGGLE TASK
# =========================================================

@login_required
def toggle_task(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user
    )


    task.completed = not task.completed

    task.save()


    return redirect("tasks")


# =========================================================
# DELETE TASK
# =========================================================

@login_required
def delete_task(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user
    )


    task.delete()


    return redirect("tasks")


# =========================================================# PROFILE
# =========================================================

@login_required
def profile(request):

    goals_count = Goal.objects.filter(
        user=request.user
    ).count()


    study_count = StudyPlan.objects.filter(
        user=request.user
    ).count()


    tasks = Task.objects.filter(
        user=request.user
    )


    tasks_count = tasks.count()


    completed_tasks = tasks.filter(
        completed=True
    ).count()


    if tasks_count > 0:

        progress = int(
            (
                completed_tasks
                / tasks_count
            ) * 100
        )

    else:

        progress = 0


    return render(
        request,
        "profile.html",
        {
            "goals_count": goals_count,
            "study_count": study_count,
            "tasks_count": tasks_count,
            "completed_tasks": completed_tasks,
            "progress": progress,
            "date_joined": request.user.date_joined,
        }
    )


# =========================================================
# EDIT PROFILE
# =========================================================

@login_required
def edit_profile(request):

    if request.method == "POST":

        email = request.POST.get(
            "email",
            ""
        ).strip()


        request.user.email = email

        request.user.save()


        return redirect("profile")


    return render(
        request,
        "edit_profile.html"
    )


# =========================================================
# CHANGE PASSWORD
# =========================================================

@login_required
def change_password(request):

    if request.method == "POST":

        old_password = request.POST.get(
            "old_password",
            ""
        )

        new_password = request.POST.get(
            "new_password",
            ""
        )

        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )


        if not request.user.check_password(
            old_password
        ):

            return render(
                request,
                "change_password.html",
                {
                    "error":
                    "Current password is incorrect."
                }
            )


        if new_password != confirm_password:

            return render(
                request,
                "change_password.html",
                {
                    "error":
                    "New passwords do not match."
                }
            )


        if len(new_password) < 6:

            return render(
                request,
                "change_password.html",
                {
                    "error":
                    "Password must be at least 6 characters."
                }
            )


        request.user.set_password(
            new_password
        )

        request.user.save()


        update_session_auth_hash(
            request,
            request.user
        )


        return redirect("profile")


    return render(
        request,
        "change_password.html"
    )