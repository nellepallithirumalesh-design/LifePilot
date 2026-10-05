from django.contrib import admin
from django.urls import path

from core import views


urlpatterns = [

    path("", views.home, name="home"),

    # Authentication
    path("login/", views.login_view, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", views.logout_view, name="logout"),

    # Dashboard
    path("dashboard/", views.dashboard, name="dashboard"),

    # profile
    path("profile/", views.profile, name="profile"),

    #edit-profile
    path("edit-profile/", views.edit_profile, name="edit_profile"),

    #password
    path("change-password/", views.change_password, name="change_password"),


    # Chat
    path("chat/", views.chat, name="chat_home"),
    path(
        "chat/<int:conversation_id>/",
        views.chat,
        name="chat"
    ),

    # New Chat
    path(
        "new-chat/",
        views.new_chat,
        name="new_chat"
    ),

    # Delete Chat
    path(
        "delete-chat/<int:conversation_id>/",
        views.delete_chat,
        name="delete_chat"
    ),

    # Clear Chat
    path(
        "clear-chat/<int:conversation_id>/",
        views.clear_chat,
        name="clear_chat"
    ),

    # Goals
    path("goals/", views.goals, name="goals"),
    path(
        "delete-goal/<int:goal_id>/",
        views.delete_goal,
        name="delete_goal"
    ),

    # Study Planner
    path("study/", views.study, name="study"),

    path(
        "delete-study-plan/<int:plan_id>/",
        views.delete_study_plan,
        name="delete_study_plan"
    ),

    # Tasks
    path("tasks/", views.tasks, name="tasks"),
    path(
        "toggle-task/<int:task_id>/",
        views.toggle_task,
        name="toggle_task"
    ),
    path(
        "delete-task/<int:task_id>/",
        views.delete_task,
        name="delete_task"
    ),

    # Career
    path("career/", views.career, name="career"),

    # Admin
    path("admin/", admin.site.urls),



]