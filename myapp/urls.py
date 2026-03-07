from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.home_page, name='home'),
    path('login/', views.login_page, name='login'),
    path('signin/', views.signin_page, name='signin'),
    path('loader/',views.loader,name='loader'),
    path('client/',views.client_page,name='client'),
    path('seller/',views.seller_page,name='seller'),
    path('myadmin/',views.admin,name='myadmin'),
    path('landing_page/',views.landing_page,name='landing_page'),
    path('seller/profile/', views.seller_profile_page, name='seller_profile'),
    path('after-login/', views.after_login, name='after_login'),
    path('seller/experience/add/', views.add_experience, name='add_experience'),
    path('seller/certificate/add/', views.add_certificate, name='add_certificate'),
    path('seller/proposal/create/', views.create_proposal, name='create_proposal'),
    path('proposals/', views.my_proposals, name='my_proposals'),
    path('faqs/',views.faqs,name='faqs'),
    path('messages/',views.messages_page,name='messages_page'),
    path('messages/send/<int:conv_id>/',views.send_message,name='send_message'),
    path('messages/check/<int:conv_id>/',views.check_new_messages, name='check_new_messages'),
    path('start-conversation/<int:seller_user_id>/', views.start_conversation, name='start_conversation'),
    path('privacy/',views.privacy,name='privacy'),
    path('about_us/',views.about_us,name='about_us'),
    path('client/profile/', views.client_profile, name='client_profile'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/<int:user_id>/', views.view_profile, name='view_profile'),
    path('review/<int:user_id>/', views.submit_review, name='submit_review'),
    path('show_seller/',views.show_seller,name='show_seller'),
    path('ai-chat/',    views.ai_chat,    name='ai_chat'),
    path('ai-context/', views.ai_context, name='ai_context'),
    
    

]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)