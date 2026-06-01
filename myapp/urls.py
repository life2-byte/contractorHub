from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # ── Existing ──
    path('', views.home_page, name='home'),
    path('login/', views.login_page, name='login'),
    path('signin/', views.signin_page, name='signin'),
    path('loader/', views.loader, name='loader'),
    path('client/', views.client_page, name='client'),
    path('seller/', views.seller_page, name='seller'),
    path('landing_page/', views.landing_page, name='landing_page'),
    path('seller/profile/', views.seller_profile_page, name='seller_profile'),
    path('after-login/', views.after_login, name='after_login'),
    path('seller/experience/add/', views.add_experience, name='add_experience'),
    path('seller/certificate/add/', views.add_certificate, name='add_certificate'),
    path('seller/proposal/create/', views.create_proposal, name='create_proposal'),
    path('proposals/', views.my_proposals, name='my_proposals'),
    path('faqs/', views.faqs, name='faqs'),
    path('messages/', views.messages_page, name='messages_page'),
    path('messages/send/<int:conv_id>/', views.send_message, name='send_message'),
    path('messages/check/<int:conv_id>/', views.check_new_messages, name='check_new_messages'),
    path('start-conversation/<int:seller_user_id>/', views.start_conversation, name='start_conversation'),
    path('privacy/', views.privacy, name='privacy'),
    path('about_us/', views.about_us, name='about_us'),
    path('client/profile/', views.client_profile, name='client_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/<int:user_id>/', views.view_profile, name='view_profile'),
    path('review/<int:user_id>/', views.submit_review, name='submit_review'),
    path('show_seller/', views.show_seller, name='show_seller'),
    path('ai-chat/', views.ai_chat, name='ai_chat'),
    path('ai-context/', views.ai_context, name='ai_context'),

    # ── Admin Panel ──
    path('myadmin/', views.admin, name='myadmin'),
    path('myadmin/users/', views.admin_users, name='admin_users'),
    path('myadmin/users/<int:user_id>/', views.admin_user_detail, name='admin_user_detail'),
    path('myadmin/users/<int:user_id>/toggle/', views.admin_toggle_user, name='admin_toggle_user'),
    path('myadmin/users/<int:user_id>/delete/', views.admin_delete_user, name='admin_delete_user'),
    path('myadmin/proposals/', views.admin_proposals, name='admin_proposals'),
    path('myadmin/proposals/<int:proposal_id>/toggle/', views.admin_toggle_proposal, name='admin_toggle_proposal'),
    path('myadmin/proposals/<int:proposal_id>/delete/', views.admin_delete_proposal, name='admin_delete_proposal'),
    path('myadmin/reviews/', views.admin_reviews, name='admin_reviews'),
    path('myadmin/reviews/<int:review_id>/delete/', views.admin_delete_review, name='admin_delete_review'),
    path('myadmin/verifications/', views.admin_verifications, name='admin_verifications'),
    path('myadmin/messages/', views.admin_messages_view, name='admin_messages'),
    path('myadmin/logs/', views.admin_logs, name='admin_logs'),
    path('myadmin/api/stats/', views.admin_stats_json, name='admin_stats_json'),
    path('password-reset/', auth_views.PasswordResetView.as_view(template_name='registration/password_reset.html'), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(template_name='registration/password_reset_done.html'), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name='registration/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(template_name='registration/password_reset_complete.html'), name='password_reset_complete'),
    path('send-email-otp/', views.send_email_otp, name='send_email_otp'),
    path('verify-email-otp/', views.verify_email_otp, name='verify_email_otp'),


] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
