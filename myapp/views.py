from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
from .models import signin
from django.contrib import messages
from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
import re, os
import urllib.request
import urllib.error
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
import json
from dotenv import load_dotenv
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate
from django.urls import reverse
import random
import string
from .models import (
    signin, Seller_Profile, Certificate, WorkExperience,
    Proposal, ProposalImpression, Message, Conversation,
    Client_Profile, Review
)
from django.utils.cache import add_never_cache_headers

class NoCacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response

load_dotenv("env.env")


# ─────────────────────────────────────────
# HELPER: Total Unread Messages
# FIX #1 — Duplicate unread-count logic extracted into one helper
# Previously copy-pasted in: client_page, client_profile, messages_page, show_seller
# ─────────────────────────────────────────
def get_total_unread(user):
    total = 0
    for conv in Conversation.objects.filter(participants=user):
        total += conv.messages.filter(is_read=False).exclude(sender=user).count()
    return total


# ─────────────────────────────────────────
# HELPER: Get seller profile photo URL
# FIX #2 — Repeated bare except + profile photo lookup extracted
# Previously copy-pasted in messages_page (twice)
# ─────────────────────────────────────────
def get_seller_photo(user):
    try:
        sp = user.seller_profile
        if sp.profile_photo:
            return sp.profile_photo.url
    except Seller_Profile.DoesNotExist:
        pass
    return None


# ─────────────────────────────────────────
# Password Validator
# ─────────────────────────────────────────
def validate_strong_password(password):
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if not re.search(r'[A-Z]', password):
        errors.append("Add at least one UPPERCASE letter (A-Z)")
    if not re.search(r'[a-z]', password):
        errors.append("Add at least one lowercase letter (a-z)")
    if not re.search(r'[0-9]', password):
        errors.append("Add at least one number (0-9)")
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>/?]', password):
        errors.append("Add at least one special character (!@#$%^&*)")
    return errors


# ─────────────────────────────────────────
# Google Login — user_type session sy lo
# ─────────────────────────────────────────
@receiver(pre_social_login)
def set_user_type_on_social_login(sender, request, sociallogin, **kwargs):
    user_type = request.session.get('user_type', 'client')

    if sociallogin.is_existing:
        user = sociallogin.user
        if not user.user_type:
            user.user_type = user_type
            user.save()
    else:
        sociallogin.user.user_type = user_type


# ─────────────────────────────────────────
# After Login Redirect
# ─────────────────────────────────────────
@login_required
def after_login(request):
    user = request.user

    if not user.user_type:
        user_type = request.session.get('user_type', 'client')
        user.user_type = user_type
        user.save()

    # FIX #3 — Removed dead code: `if not request.user.is_authenticated`
    # @login_required already guarantees the user is authenticated — that check was unreachable
    if user.user_type.lower() == 'contractor':
        return redirect('seller')
    return redirect('client')


# ─────────────────────────────────────────
# Landing Page — Role Select
# ─────────────────────────────────────────
def landing_page(request):
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        request.session['user_type'] = user_type
        return redirect(f'/signin/?user_type={user_type}')
    return render(request, 'landingpage.html')


# ─────────────────────────────────────────
# Signup Page
# ─────────────────────────────────────────
def login_page(request):
    context = {}
    # POST request mein bhi milega
    user_type = request.POST.get('user_type') or request.GET.get('user_type') or request.session.get('user_type', 'client')

    if request.method == 'POST':
        name           = request.POST.get("name")
        email          = request.POST.get("email")
        phone          = request.POST.get("phone")
        password       = request.POST.get("password")
        confirmed_pass = request.POST.get("confirm_password")

        context['form_data'] = {'name': name, 'email': email, 'phone': phone}
        field_errors = {}

        if not name or not email or not phone or not password or not confirmed_pass:
            messages.error(request, "All fields are required!")
            if not name:           field_errors['name']             = "Name is required"
            if not email:          field_errors['email']            = "Email is required"
            if not phone:          field_errors['phone']            = "Phone is required"
            if not password:       field_errors['password']         = "Password is required"
            if not confirmed_pass: field_errors['confirm_password'] = "Please confirm your password"

        elif password != confirmed_pass:
            messages.error(request, "Passwords do not match!")
            field_errors['password']         = "Passwords do not match"
            field_errors['confirm_password'] = "Passwords do not match"

        else:
            password_errors = validate_strong_password(password)
            if password_errors:
                for error in password_errors:
                    messages.error(request, error)
                field_errors['password'] = "Password is not strong enough"

            elif phone and not phone.isdigit():
                messages.error(request, "Phone number should contain only digits!")
                field_errors['phone'] = "Only digits allowed"

            elif signin.objects.filter(email=email).exists():
                messages.error(request, "Email already exists!")
                field_errors['email'] = "This email is already registered"

            else:
                try:
                    user = signin.objects.create_user(
                        email=email,
                        name=name,
                        password=password,
                        phone=phone,
                        user_type=user_type
                    )
                    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                    messages.success(request, "Account created successfully!")

                    if user_type and user_type.lower() == 'contractor':
                        return redirect('seller')
                    return redirect('client')

                except Exception as e:
                    print("ERROR:", str(e))
                    messages.error(request, f"Error: {str(e)}")

        context['field_errors'] = field_errors

    return render(request, 'login.html', context)


# ─────────────────────────────────────────
# Signin Page
# ─────────────────────────────────────────
def signin_page(request):
    field_errors = {}

    if request.method == 'POST':
        email    = request.POST.get("email")
        password = request.POST.get("password")

        if not email or not password:
            messages.error(request, "All fields are required!")
            if not email:    field_errors['email']    = "Email is required"
            if not password: field_errors['password'] = "Password is required"
        else:
            try:
                user = authenticate(request, email=email, password=password)
                if user is not None:
                    login(request, user)
                    if user.is_superuser:
                        return redirect('myadmin')
                    elif user.user_type and user.user_type.lower() == 'contractor':
                        return redirect('seller')
                    return redirect('client')
                else:
                    messages.error(request, "Invalid credentials!")
            except Exception as e:
                messages.error(request, "Authentication failed!")

    return render(request, 'login.html', {'field_errors': field_errors})


# ─────────────────────────────────────────
# Home Page
# ─────────────────────────────────────────
def home_page(request):
    from django.db.models import Avg
    
    # Top contractors — avg_rating se sorted, jo available hain aur proposals bhi hain
    top_contractors = Seller_Profile.objects.filter(
        is_available=True,
        user__user_type='contractor'
    ).select_related('user').prefetch_related('proposals').order_by('-avg_rating')
    
    # Sirf woh jo active proposals rakhte hain
    top_contractors = [s for s in top_contractors if s.proposals.filter(is_active=True).exists()][:3]
    
    total_contractors = Seller_Profile.objects.filter(
        is_available=True, user__user_type='contractor'
    ).count()
    
    from .models import Proposal, Review
    total_proposals = Proposal.objects.filter(is_active=True).count()
    
    avg_r = Review.objects.aggregate(Avg('rating'))['rating__avg']
    avg_rating = round(avg_r, 1) if avg_r else None
    
    return render(request, 'home.html', {
        'top_contractors': top_contractors,
        'total_contractors': total_contractors,
        'total_proposals': total_proposals,
        'avg_rating': avg_rating,
    })


# ─────────────────────────────────────────
# Loader
# ─────────────────────────────────────────
def loader(request):
    return render(request, 'loader.html')


# ─────────────────────────────────────────
# Client Dashboard
# ─────────────────────────────────────────
def fuzzy_search_filter(workers, search_query):
    from difflib import SequenceMatcher
    from django.db.models import Q
    
    def similarity(a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()
    
    base_results = workers.filter(
        Q(user__name__icontains=search_query) |
        Q(skills__icontains=search_query)     |
        Q(city__icontains=search_query)        |
        Q(title__icontains=search_query)       |
        Q(proposals__title__icontains=search_query)      |
        Q(proposals__search_tag__icontains=search_query) |
        Q(proposals__work_type__icontains=search_query)
    ).distinct()
    
    all_workers = workers.exclude(
        id__in=base_results.values_list('id', flat=True)
    )
    
    fuzzy_ids = []
    for w in all_workers:
        fields_to_check = [
            w.title or '',
            w.skills or '',
            w.city or '',
            w.user.name or '',
        ]
        for p in w.proposals.filter(is_active=True):
            fields_to_check += [p.title or '', p.search_tag or '', p.work_type or '']
        
        found = False
        for field in fields_to_check:
            for word in field.split():
                if len(word) >= 4 and len(search_query) >= 4:
                    if similarity(search_query, word) >= 0.72:
                        fuzzy_ids.append(w.id)
                        found = True
                        break
            if found:
                break
    
    combined_ids = list(base_results.values_list('id', flat=True)) + fuzzy_ids
    
    if not combined_ids:
        return workers.none()
    
    return workers.filter(id__in=combined_ids).distinct()


from django.db.models import Prefetch
@login_required
def client_page(request):
    if not request.user.user_type:
        return redirect('landing_page')
    if request.user.user_type.lower() == 'contractor':
        return redirect('seller')

    search_query = request.GET.get('search', '')
    category     = request.GET.get('category', '')

    workers = Seller_Profile.objects.filter(
        is_available=True,
        user__user_type='contractor'
    ).select_related('user').prefetch_related(
        Prefetch(
            'proposals',
            queryset=Proposal.objects.filter(is_active=True),
            to_attr='active_proposals_list'
        )
    )

    if search_query:
        workers = fuzzy_search_filter(workers, search_query)  # ← yahan change hua

    if category:
        workers = workers.filter(
            Q(skills__icontains=category)                    |
            Q(proposals__title__icontains=category)          |
            Q(proposals__search_tag__icontains=category)
        ).distinct()

    workers = list(workers.order_by('-avg_rating'))
    workers = [w for w in workers if w.active_proposals_list][:6]

    context = {
        'workers':             workers,
        'search_query':        search_query,
        'category':            category,
        'total_unread':        get_total_unread(request.user),
        'notifications_count': 0,
    }
    return render(request, 'client.html', context)
# ─────────────────────────────────────────
# Client Profile
# ─────────────────────────────────────────
@login_required
def client_profile(request):
    # FIX #3 — Removed dead `if not request.user.is_authenticated` check

    if request.user.user_type and request.user.user_type.lower() == 'contractor':
        return redirect('seller_profile')

    client_profile_obj, _ = Client_Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        client_profile_obj.city     = request.POST.get('city', '')
        client_profile_obj.language = request.POST.get('language', '')

        if request.FILES.get('profile_photo'):
            client_profile_obj.profile_photo = request.FILES['profile_photo']

        client_profile_obj.save()
        messages.success(request, 'Profile updated successfully!')
        return redirect('client_profile')

    profile_complete = 50
    if client_profile_obj.city:     profile_complete += 25
    if client_profile_obj.language: profile_complete += 25

    my_reviews = Review.objects.filter(
        seller=request.user
    ).select_related('client').order_by('-created_at')

    avg_rating = None
    if my_reviews.exists():
        avg        = my_reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)

    context = {
        'user':             request.user,
        'client_profile':   client_profile_obj,
        'profile_complete': profile_complete,
        'total_unread':     get_total_unread(request.user),   # FIX #1
        'my_reviews':       my_reviews,
        'avg_rating':       avg_rating,
    }
    return render(request, 'client_profile.html', context)


# ─────────────────────────────────────────
# Seller / Contractor Dashboard
# ─────────────────────────────────────────
@login_required
def seller_page(request):
    # FIX #3 — Removed dead `if not request.user.is_authenticated` check

    if not request.user.user_type:
        return redirect('landing_page')
    
    if request.user.user_type.lower() != 'contractor':
        return redirect('client')
    

    profile, _ = Seller_Profile.objects.get_or_create(user=request.user)

    active_proposals  = Proposal.objects.filter(seller=profile, is_active=True)
    active_bids_count = active_proposals.count()

    level_names = {
        1: "Beginner",   2: "Apprentice", 3: "Journeyman",
        4: "Skilled Worker", 5: "Craftsman",  6: "Expert",
        7: "Specialist", 8: "Master",     9: "Grand Master", 10: "Legend"
    }
    level_name = level_names.get(profile.level, f"Level {profile.level}")

    current_xp    = profile.level * 800 + 200
    next_level_xp = (profile.level + 1) * 1000
    xp_percentage = int((current_xp / next_level_xp) * 100)

    recent_proposals = Proposal.objects.filter(
        seller=profile
    ).order_by('-created_at')[:3]

    context = {
        'profile':                  profile,
        'active_bids_count':        active_bids_count,
        'active_projects_count':    active_bids_count,
        'active_projects_change':   0,
        'pending_proposals_count':  active_bids_count,
        'pending_proposals_change': 0,
        'level_name':               level_name,
        'current_xp':               current_xp,
        'next_level_xp':            next_level_xp,
        'xp_percentage':            xp_percentage,
        'recent_proposals':         recent_proposals,
    }
    return render(request, 'seller.html', context)




# ─────────────────────────────────────────
# Seller Profile Page
# ─────────────────────────────────────────
@login_required
def seller_profile_page(request):
    if not request.user.user_type or request.user.user_type.lower() != 'contractor':
        return redirect('landing_page')
    profile, _ = Seller_Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':

        if request.POST.get('availability_only'):
            profile.is_available = request.POST.get('is_available') == 'on'
            profile.save()
            return redirect('seller_profile')

        # ── Location only (map se) ──
        if request.POST.get('location_only'):
            profile.city = request.POST.get('city', '')
            profile.area = request.POST.get('area', '')  # naya
            profile.save()
            return redirect('seller_profile')

        name = request.POST.get('name', '').strip()
        if name:
            request.user.name = name
            request.user.save()

        profile.title        = request.POST.get('title', '')
        profile.city         = request.POST.get('city', '')
        profile.area         = request.POST.get('area', '')  # naya
        profile.language     = request.POST.get('language', '')
        profile.about        = request.POST.get('about', '')
        profile.skills       = request.POST.get('skills', '')
        profile.is_available = request.POST.get('is_available') == 'on'

        if request.FILES.get('profile_photo'):
            profile.profile_photo = request.FILES['profile_photo']
        if request.FILES.get('cover_photo'):
            profile.cover_photo = request.FILES['cover_photo']

        profile.save()
        messages.success(request, "Profile updated successfully!")
        return redirect('seller_profile')

    reviews       = Review.objects.filter(seller=request.user).select_related('client').order_by('-created_at')
    reviews_count = reviews.count()
    avg_rating    = None
    if reviews_count:
        avg        = reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)

    jobs_count = Proposal.objects.filter(seller=profile).count()

    context = {
        'user':          request.user,
        'profile':       profile,
        'experiences':   profile.experiences.all(),
        'certificates':  profile.certificates.all(),
        'reviews':       reviews,
        'avg_rating':    avg_rating,
        'reviews_count': reviews_count,
        'jobs_count':    jobs_count,
    }
    return render(request, 'profile_seller.html', context)

# ─────────────────────────────────────────
# Add Experience
# ─────────────────────────────────────────
@login_required
def add_experience(request):
    if request.method == 'POST':
        profile = request.user.seller_profile

        start_raw  = request.POST.get('start_date')
        end_raw    = request.POST.get('end_date')
        start_date = f"{start_raw}-01" if start_raw else None
        end_date   = f"{end_raw}-01"   if end_raw   else None

        WorkExperience.objects.create(
            seller      = profile,
            job_title   = request.POST.get('job_title'),
            company     = request.POST.get('company'),
            city        = request.POST.get('city', ''),
            start_date  = start_date,
            end_date    = end_date,
            is_current  = request.POST.get('is_current') == 'on',
            description = request.POST.get('description', '')
        )
        return redirect('seller_profile')


# ─────────────────────────────────────────
# Add Certificate
# ─────────────────────────────────────────
@login_required
def add_certificate(request):
    if request.method == 'POST':
        profile = request.user.seller_profile
        Certificate.objects.create(
            seller=profile,
            title=request.POST.get('title'),
            file=request.FILES.get('file')
        )
        return redirect('seller_profile')


# ─────────────────────────────────────────
# Create Proposal
# ─────────────────────────────────────────
@login_required
def create_proposal(request):
    if not request.user.user_type or request.user.user_type.lower() != 'contractor':
        return redirect('landing_page')
    
    profile = request.user.seller_profile
    if request.method == 'POST':
        Proposal.objects.create(
            seller          = profile,
            title           = request.POST.get('title'),
            description     = request.POST.get('description', ''),
            search_tag      = request.POST.get('search_tag', ''),
            work_type       = request.POST.get('work_type'),
            base_price      = request.POST.get('base_price'),
            delivery_time   = request.POST.get('delivery_time', ''),
            portfolio_image = request.FILES.get('portfolio_image'),
            doc_portfolio   = request.FILES.get('doc_portfolio'),
            video_intro     = request.FILES.get('video_intro'),
            is_active       = request.POST.get('is_active') == 'true',
        )
        messages.success(request, "Proposal published successfully!")
        return redirect('seller_profile')

    context = {'user': request.user, 'profile': profile}
    return render(request, 'proposal.html', context)


# ─────────────────────────────────────────
# My Proposals
# ─────────────────────────────────────────
@login_required
def my_proposals(request):
    profile   = request.user.seller_profile
    proposals = Proposal.objects.filter(seller=profile).order_by('-created_at')

    total_proposals   = proposals.count()
    active_count      = proposals.filter(is_active=True).count()
    total_impressions = ProposalImpression.objects.filter(proposal__seller=profile).count()

    proposals_list = [
        {
            'id':            p.id,
            'title':         p.title,
            'work_type':     p.work_type,
            'base_price':    str(p.base_price),
            'delivery_time': p.delivery_time,
            'search_tag':    p.search_tag,
            'is_active':     p.is_active,
            'created_at':    p.created_at.strftime('%b %d, %Y'),
        }
        for p in proposals
    ]

    impressions_dict = {}
    today = timezone.now().date()

    for p in proposals:
        imp_qs = ProposalImpression.objects.filter(proposal=p)

        daily_qs = (
            imp_qs
            .annotate(day=TruncDate('viewed_at'))
            .values('day')
            .annotate(count=Count('id'))
        )
        daily = {str(row['day']): row['count'] for row in daily_qs}

        impressions_dict[p.id] = {
            'total': imp_qs.count(),
            'today': imp_qs.filter(viewed_at__date=today).count(),
            'week':  imp_qs.filter(viewed_at__date__gte=today - timezone.timedelta(days=7)).count(),
            'month': imp_qs.filter(viewed_at__date__gte=today - timezone.timedelta(days=30)).count(),
            'daily': daily,
        }

    context = {
        'profile':           profile,
        'proposals':         proposals,
        'total_proposals':   total_proposals,
        'active_count':      active_count,
        'total_impressions': total_impressions,
        'proposals_json':    json.dumps(proposals_list),
        'impressions_json':  json.dumps(impressions_dict),
    }
    return render(request, 'active_work.html', context)


# ─────────────────────────────────────────
# Static pages
# FIX #5 — Renamed parameter `requests` → `request` in faqs, privacy, about_us
# ─────────────────────────────────────────
def faqs(request):
    return render(request, 'faqs.html')


def privacy(request):
    return render(request, 'privacy.html')


def about_us(request):
    return render(request, 'about_us.html')


# ─────────────────────────────────────────
# Messages Page
# ─────────────────────────────────────────
@login_required
def messages_page(request):
    user = request.user

    conversations = Conversation.objects.filter(
        participants=user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')

    conv_data = []
    for conv in conversations:
        other_user = conv.get_other_user(user)
        if not other_user:
            continue

        conv_data.append({
            'id':                       conv.id,
            'other_user':               other_user,
            'other_user_profile_photo': get_seller_photo(other_user),   # FIX #2
            'last_message':             conv.messages.last(),
            'last_message_time':        conv.updated_at,
            'unread_count':             conv.get_unread_count(user),
            'is_online':                False,
            'last_seen':                conv.updated_at,
        })

    active_conv_data = None
    messages_list    = []
    last_message_id  = 0
    conv_id          = request.GET.get('conv')

    if conv_id:
        try:
            active_conv_obj = Conversation.objects.get(id=conv_id, participants=user)
            other_user      = active_conv_obj.get_other_user(user)

            active_conv_data = {
                'id':                       active_conv_obj.id,
                'other_user':               other_user,
                'other_user_profile_photo': get_seller_photo(other_user),   # FIX #2
                'is_online':                False,
                'last_seen':                active_conv_obj.updated_at,
            }

            messages_list = active_conv_obj.messages.select_related('sender', 'proposal').all()
            if messages_list.exists():
                last_message_id = messages_list.last().id

            active_conv_obj.messages.filter(
                is_read=False
            ).exclude(sender=user).update(is_read=True)

        except Conversation.DoesNotExist:
            pass

    total_unread = sum(c['unread_count'] for c in conv_data)

    try:
        profile = user.seller_profile
    except Seller_Profile.DoesNotExist:        # FIX #2 — specific exception, not bare except
        profile = None

    my_proposals_qs = []
    if profile:
        my_proposals_qs = Proposal.objects.filter(seller=profile, is_active=True)

    context = {
        'profile':          profile,
        'conversations':    conv_data,
        'active_conv':      active_conv_data,
        'messages':         messages_list,
        'total_unread':     total_unread,
        'my_proposals':     my_proposals_qs,
        'last_message_id':  last_message_id,
    }
    return render(request, 'messages.html', context)


# ─────────────────────────────────────────
# Send Message
# ─────────────────────────────────────────
@login_required
@require_POST
def send_message(request, conv_id):
    conv = get_object_or_404(Conversation, id=conv_id, participants=request.user)

    if request.user.user_type == 'contractor' and not request.user.is_superuser:
        if not conv.messages.exists():
            return redirect('messages_page')

    content = request.POST.get('content', '').strip()
    if not content:
        return redirect(f"/messages/?conv={conv_id}")

    proposal    = None
    proposal_id = request.POST.get('proposal_id', '').strip()
    if proposal_id:
        try:
            proposal = Proposal.objects.get(id=proposal_id)
        except Proposal.DoesNotExist:
            pass

    Message.objects.create(
        conversation=conv,
        sender=request.user,
        content=content,
        proposal=proposal,
    )

    conv.updated_at = timezone.now()
    conv.save()

    return redirect(f"/messages/?conv={conv_id}")


# ─────────────────────────────────────────
# Check New Messages — JS polling
# ─────────────────────────────────────────
@login_required
def check_new_messages(request, conv_id):
    try:
        conv      = Conversation.objects.get(id=conv_id, participants=request.user)
        last_id   = int(request.GET.get('last_id', 0))
        new_msgs  = conv.messages.filter(id__gt=last_id).exclude(sender=request.user)
        has_new   = new_msgs.exists()
        latest    = conv.messages.last()
        latest_id = latest.id if latest else 0

        return JsonResponse({'has_new': has_new, 'latest_id': latest_id, 'is_typing': False})

    except Conversation.DoesNotExist:
        return JsonResponse({'has_new': False, 'latest_id': 0, 'is_typing': False})
    except Exception:
        return JsonResponse({'has_new': False, 'latest_id': 0, 'is_typing': False})


# ─────────────────────────────────────────
# View Profile
# ─────────────────────────────────────────
@login_required
def view_profile(request, user_id):
    target_user      = get_object_or_404(signin, id=user_id)
    seller_profile   = None
    client_profile   = None
    experiences      = []
    certificates     = []
    active_proposals = []
    level_name       = "Beginner"

    if target_user.user_type and target_user.user_type.lower() == 'contractor':
        seller_profile   = get_object_or_404(Seller_Profile, user=target_user)
        experiences      = seller_profile.experiences.all()
        certificates     = seller_profile.certificates.all()
        active_proposals = seller_profile.proposals.filter(is_active=True)
        level_map        = {1: 'Beginner', 2: 'Intermediate', 3: 'Expert'}
        level_name       = level_map.get(seller_profile.level, 'Beginner')
    else:
        try:
            client_profile = Client_Profile.objects.get(user=target_user)
        except Client_Profile.DoesNotExist:    # FIX #2 — specific exception
            client_profile = None

    reviews = Review.objects.filter(
        seller=target_user
    ).select_related('client').order_by('-created_at')

    user_review = None
    if request.user.is_authenticated and request.user != target_user:
        user_review = Review.objects.filter(
            seller=target_user,
            client=request.user
        ).first()

    return render(request, 'profile_view.html', {
        'target_user':      target_user,
        'seller_profile':   seller_profile,
        'client_profile':   client_profile,
        'experiences':      experiences,
        'certificates':     certificates,
        'active_proposals': active_proposals,
        'level_name':       level_name,
        'reviews':          reviews,
        'user_review':      user_review,
    })


# ─────────────────────────────────────────
# Start Conversation — Client/Admin only
# ─────────────────────────────────────────
@login_required
def start_conversation(request, seller_user_id):
    if request.user.user_type == 'contractor' and not request.user.is_superuser:
        return redirect('messages_page')

    seller_user = get_object_or_404(signin, id=seller_user_id)

    if seller_user == request.user:
        return redirect('messages_page')

    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=seller_user
    ).first()

    if not conv:
        conv = Conversation.objects.create(started_by=request.user)
        conv.participants.add(request.user, seller_user)

    # FIX #6 — Use reverse() instead of hardcoded URL string
    return redirect(f"{reverse('messages_page')}?conv={conv.id}")


# ─────────────────────────────────────────
# Logout
# ─────────────────────────────────────────
def logout_view(request):
    logout(request)
    return redirect('landing_page')


# ─────────────────────────────────────────
# Submit Review
# ─────────────────────────────────────────
@login_required
def submit_review(request, user_id):
    if request.method != 'POST':
        return redirect('view_profile', user_id=user_id)

    target_user = get_object_or_404(signin, id=user_id)

    if request.user == target_user:
        return redirect('view_profile', user_id=user_id)

    rating  = max(1, min(5, int(request.POST.get('rating', 5))))
    comment = request.POST.get('comment', '').strip()

    Review.objects.update_or_create(
        seller=target_user,
        client=request.user,
        defaults={'rating': rating, 'comment': comment}
    )

    if target_user.user_type and target_user.user_type.lower() == 'contractor':
        avg = Review.objects.filter(seller=target_user).aggregate(Avg('rating'))['rating__avg']
        Seller_Profile.objects.filter(user=target_user).update(avg_rating=round(avg, 1))

    return redirect('view_profile', user_id=user_id)


# ─────────────────────────────────────────
# Show Sellers
# FIX #6 — Replaced hardcoded URL strings with reverse()
# ─────────────────────────────────────────
@login_required
def show_seller(request):
    if request.user.user_type and request.user.user_type.lower() == 'contractor':
        return redirect('seller')

    workers = Seller_Profile.objects.filter(
        is_available=True,
        user__user_type='contractor'
    ).select_related('user').prefetch_related('proposals')

    workers_data = []
    for w in workers:
        active_proposals = w.proposals.filter(is_active=True)
        
        # Koi proposal nahi to skip karo
        if not active_proposals.exists():
            continue
        
        # Har proposal ka alag entry banao
        for proposal in active_proposals:
            price         = str(proposal.base_price)
            proposal_image = proposal.portfolio_image.url if proposal.portfolio_image else ''

            workers_data.append({
                'id':            w.user.id,
                'name':          w.user.name or '',
                'title':         w.title or '',
                'skills':        w.skills or '',
                'city':          w.city or '',
                'rating':        float(w.avg_rating) if w.avg_rating else 4.5,
                'price':         price,
                'photo':         w.profile_photo.url if w.profile_photo else '',
                'profile_url':   reverse('view_profile', args=[w.user.id]),
                'message_url':   reverse('start_conversation', args=[w.user.id]),
                'gig_title':     proposal.title,
                'proposal_desc': (proposal.description or '')[:120],
                'proposal_image': proposal_image,
            })

    return render(request, 'show_seller.html', {
        'workers_json': json.dumps(workers_data, ensure_ascii=False),
        'total_unread': get_total_unread(request.user),
    })

# ─────────────────────────────────────────
# AI SYSTEM PROMPTS
# ─────────────────────────────────────────

CLIENT_SYSTEM_PROMPT = """
You are ContractorHub's AI assistant for CLIENTS (job-givers/employers).

Your job:
1. Help clients find the best contractor for their specific need
2. Ask smart questions to understand their project (type of work, city, budget, timeline)
3. From the worker data provided, recommend the TOP 2-3 best matches with clear reasons
4. Give advice on how to evaluate contractors, what to check before hiring
5. Explain what a fair price looks like for their type of job in Pakistan

Worker data will be provided to you in JSON format. Use it to make personalized recommendations.

IMPORTANT RULES:
- Always respond in the SAME language the user writes in (Urdu/Roman Urdu/English)
- Be conversational, friendly, like a helpful friend — not robotic
- When recommending workers, mention their name, skills, city, rating, and WHY they're a good fit
- If no workers match, suggest what to search for or broaden criteria
- Keep responses concise — max 3-4 short paragraphs
- Do NOT make up worker data — only use what's provided
- Format worker recommendations clearly with bullet points or numbering

Platform context: ContractorHub connects skilled contractors (plumbers, electricians,
painters, carpenters, masons, etc.) with clients in Pakistan.
"""

SELLER_SYSTEM_PROMPT = """
You are ContractorHub's AI coach for CONTRACTORS/SELLERS (service providers).

Your job: Help contractors maximize their profile quality and win more clients.

PROFILE COACHING:
- Review their current profile data (provided as JSON)
- Suggest specific improvements to: title, bio/about, skills list
- Explain what clients look for when choosing a contractor

PROPOSAL/GIG COACHING:
When they ask about proposals/gigs, advise on:

📸 PORTFOLIO IMAGE:
- Show "before & after" of actual work (e.g., before messy wiring → after clean install)
- Use bright natural lighting, landscape orientation
- Include yourself in the photo for trust (wearing work clothes/uniform)
- For painters: show color swatches + painted wall
- For plumbers: show pipe work clearly, no blur
- Add a simple text overlay: your name + specialty

📄 DOCUMENTS:
- Upload any trade license, experience certificate, or training certificate
- Even a reference letter from a past client works
- CNIC copy is powerful for trust — clients feel safe
- A typed "work guarantee" document (1-page) impresses clients a lot

🎥 VIDEO INTRODUCTION (highly recommended):
- 30-60 seconds max, filmed vertically on phone is fine
- Script: "Assalam alaikum, main [name] hoon, [city] se. Mujhe [X] saal ka tajruba hai [skill] mein..."
- Show your workspace/tools briefly in background
- Smile and speak clearly — personality matters
- Say your price range and availability at the end
- Upload to proposals as video_intro

PRICING ADVICE:
- New contractors: price 10-15% below market to get first reviews
- After 5+ reviews: increase to market rate
- Always mention "free estimate/visit" in description

IMPORTANT RULES:
- Respond in SAME language as user (Urdu/Roman Urdu/English)
- Be encouraging and specific — not generic
- Reference their actual profile data when coaching (name, current skills, etc.)
- Give actionable step-by-step advice, not vague tips
- Max 3-4 short paragraphs or a clear numbered list
"""


# ─────────────────────────────────────────
# HELPER: Build AI context for Client
# ─────────────────────────────────────────
def _build_client_context(request):
    workers = Seller_Profile.objects.filter(
        is_available=True,
        user__user_type='contractor'
    ).select_related('user').prefetch_related('proposals')

    workers_data = []
    for w in workers:
        first_proposal = w.proposals.filter(is_active=True).first()
        price = str(first_proposal.base_price) if first_proposal else 'Not specified'
        workers_data.append({
            'name':        w.user.name or 'Unknown',
            'title':       w.title or '',
            'skills':      w.skills or '',
            'city':        w.city or '',
            'rating':      float(w.avg_rating) if w.avg_rating else None,
            'price':       price,
            'profile_url': reverse('view_profile', args=[w.user.id]),   # FIX #6
            'about':       (w.about or '')[:200],
        })

    return {
        'user_name':       request.user.name or 'Client',
        'user_city':       '',
        'available_workers': workers_data,
        'total_workers':   len(workers_data),
    }


# ─────────────────────────────────────────
# HELPER: Build AI context for Seller
# ─────────────────────────────────────────
def _build_seller_context(request):
    try:
        profile = request.user.seller_profile
    except Seller_Profile.DoesNotExist:        # FIX #2 — specific exception
        return {'user_name': request.user.name or 'Contractor'}

    reviews    = Review.objects.filter(seller=request.user)
    avg_rating = None
    if reviews.exists():
        avg        = reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)

    proposals      = Proposal.objects.filter(seller=profile, is_active=True)
    proposals_data = [{
        'title':        p.title,
        'description':  (p.description or '')[:150],
        'price':        str(p.base_price),
        'work_type':    p.work_type,
        'has_image':    bool(p.portfolio_image),
        'has_video':    bool(p.video_intro),
        'has_document': bool(p.doc_portfolio),
    } for p in proposals]

    return {
        'user_name':         request.user.name or 'Contractor',
        'title':             profile.title or 'Not set',
        'skills':            profile.skills or 'Not set',
        'about':             profile.about or 'Not written',
        'city':              profile.city or 'Not set',
        'level':             profile.level,
        'is_available':      profile.is_available,
        'avg_rating':        avg_rating,
        'total_reviews':     reviews.count(),
        'has_profile_photo': bool(profile.profile_photo),
        'has_cover_photo':   bool(profile.cover_photo),
        'active_proposals':  proposals_data,
        'total_proposals':   proposals.count(),
    }


# ─────────────────────────────────────────
# HELPER: Call Groq API
# ─────────────────────────────────────────
def _call_groq(system_prompt, messages_history, api_key):
    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        msgs = [{"role": "system", "content": system_prompt}] + messages_history

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=msgs,
            max_tokens=800,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip(), None

    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────
# AI Context — initial load
# ─────────────────────────────────────────
@login_required
def ai_context(request):
    user = request.user
    role = 'seller' if (user.user_type and user.user_type.lower() == 'contractor') else 'client'

    if role == 'client':
        ctx = _build_client_context(request)
        welcome = (
            f"Assalam alaikum {ctx['user_name']}! 👋\n\n"
            f"Main aapka AI assistant hoon. Abhi {ctx['total_workers']} contractors available hain "
            f"ContractorHub pe.\n\n"
            f"Batayein — aapko kis kaam ke liye contractor chahiye? "
            f"(maslan: plumber, electrician, painter) aur kaunse city mein?"
        )
    else:
        ctx = _build_seller_context(request)
        welcome = (
            f"Assalam alaikum {ctx['user_name']}! 🛠️\n\n"
            f"Main aapka profile coach hoon. Main aapko help karunga:\n"
            f"• Profile improve karein (skills, bio, title)\n"
            f"• Proposal photos/videos ke tips\n"
            f"• More clients attract karein\n\n"
            f"Kya improve karna chahte ho aaj?"
        )

    return JsonResponse({'role': role, 'context': ctx, 'welcome': welcome})


# ─────────────────────────────────────────
# AI Chat — main endpoint
# ─────────────────────────────────────────
@login_required
@require_POST
def ai_chat(request):
    from django.conf import settings

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'reply': '', 'error': 'Invalid JSON'}, status=400)

    user_message = body.get('message', '').strip()
    history      = body.get('history', [])

    if not user_message:
        return JsonResponse({'reply': '', 'error': 'Empty message'}, status=400)

    user      = request.user
    is_seller = user.user_type and user.user_type.lower() == 'contractor'

    if is_seller:
        ctx           = _build_seller_context(request)
        system_prompt = SELLER_SYSTEM_PROMPT + f"\n\nCurrent seller profile data:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"
    else:
        ctx           = _build_client_context(request)
        system_prompt = CLIENT_SYSTEM_PROMPT + f"\n\nAvailable workers on platform right now:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"

    recent_history   = history[-8:]
    messages_payload = recent_history + [{"role": "user", "content": user_message}]

    api_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API') or os.environ.get('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'reply': '', 'error': 'GROQ_API_KEY not configured in settings.py'}, status=500)

    reply, error = _call_groq(system_prompt, messages_payload, api_key)

    if error:
        return JsonResponse({'reply': '', 'error': error}, status=500)

    return JsonResponse({'reply': reply, 'error': None})



# ─────────────────────────────────────────
# Admin Panel
# FIX #4 — Added @login_required + superuser check
# Previously unprotected — anyone could access /myadmin/
# ─────────────────────────────────────────
# ─────────────────────────────────────────
# HELPER: Superuser check decorator
# ─────────────────────────────────────────
def superuser_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            return redirect('landing_page')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ─────────────────────────────────────────
# HELPER: Get initials from name
# ─────────────────────────────────────────
def get_initials(name):
    if not name:
        return "??"
    parts = name.strip().split()
    return (parts[0][0] + (parts[1][0] if len(parts) > 1 else parts[0][1])).upper()


# ─────────────────────────────────────────
# REPLACE existing admin() view with this
# (old one had no superuser check)
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin(request):
    today = timezone.now().date()

    total_users      = signin.objects.count()
    total_workers    = signin.objects.filter(user_type='contractor').count()
    total_clients    = signin.objects.filter(user_type='client').count()
    new_today        = signin.objects.filter(date_joined__date=today).count()
    total_proposals  = Proposal.objects.count()
    active_proposals = Proposal.objects.filter(is_active=True).count()
    total_messages   = Message.objects.count()
    total_convs      = Conversation.objects.count()
    total_reviews    = Review.objects.count()
    avg_r            = Review.objects.aggregate(Avg('rating'))['rating__avg']
    avg_rating       = round(avg_r, 1) if avg_r else 0

    # Last 6 months signup chart data
    monthly_signups = []
    for i in range(5, -1, -1):
        month = (today.replace(day=1) - timezone.timedelta(days=i * 30))
        count = signin.objects.filter(
            date_joined__year=month.year,
            date_joined__month=month.month
        ).count()
        monthly_signups.append({'month': month.strftime('%b'), 'count': count})

    context = {
        'total_users':       total_users,
        'total_workers':     total_workers,
        'total_clients':     total_clients,
        'new_today':         new_today,
        'total_proposals':   total_proposals,
        'active_proposals':  active_proposals,
        'total_messages':    total_messages,
        'total_convs':       total_convs,
        'total_reviews':     total_reviews,
        'avg_rating':        avg_rating,
        'recent_users':      signin.objects.order_by('-date_joined')[:8],
        'recent_reviews':    Review.objects.select_related('client', 'seller').order_by('-created_at')[:5],
        'monthly_signups':   json.dumps(monthly_signups),
    }
    return render(request, 'admin.html', context)


# ─────────────────────────────────────────
# Admin: Users List
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_users(request):
    search = request.GET.get('search', '')
    utype  = request.GET.get('type', '')
    status = request.GET.get('status', '')

    users = signin.objects.order_by('-date_joined')
    if search:
        users = users.filter(Q(name__icontains=search) | Q(email__icontains=search) | Q(phone__icontains=search))
    if utype:
        users = users.filter(user_type=utype)
    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'suspended':
        users = users.filter(is_active=False)

    return render(request, 'admin.html', {
        'section': 'users',
        'users': users,
        'search': search, 'utype': utype, 'status': status,
    })


# ─────────────────────────────────────────
# Admin: User Detail
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_user_detail(request, user_id):
    target = get_object_or_404(signin, id=user_id)

    seller_profile, proposals, certificates, experiences = None, [], [], []
    try:
        seller_profile = target.seller_profile
        proposals      = Proposal.objects.filter(seller=seller_profile).order_by('-created_at')
        certificates   = seller_profile.certificates.all()
        experiences    = seller_profile.experiences.all()
    except Seller_Profile.DoesNotExist:
        pass

    reviews = Review.objects.filter(seller=target).select_related('client').order_by('-created_at')
    avg_r   = reviews.aggregate(Avg('rating'))['rating__avg']

    return render(request, 'admin.html', {
        'section':        'user_detail',
        'target':         target,
        'seller_profile': seller_profile,
        'proposals':      proposals,
        'reviews':        reviews,
        'avg_rating':     round(avg_r, 1) if avg_r else None,
        'certificates':   certificates,
        'experiences':    experiences,
        'convs':          Conversation.objects.filter(participants=target).order_by('-updated_at')[:5],
    })


# ─────────────────────────────────────────
# Admin: Toggle User Active/Suspend (AJAX)
# ─────────────────────────────────────────
@login_required
@superuser_required
@require_POST
def admin_toggle_user(request, user_id):
    user = get_object_or_404(signin, id=user_id)
    if user.is_superuser:
        return JsonResponse({'error': 'Cannot modify superuser'}, status=403)
    user.is_active = not user.is_active
    user.save()
    return JsonResponse({
        'success': True,
        'is_active': user.is_active,
        'message': f"{'Activated' if user.is_active else 'Suspended'}: {user.name}"
    })


# ─────────────────────────────────────────
# Admin: Delete User (AJAX)
# ─────────────────────────────────────────
@login_required
@superuser_required
@require_POST
def admin_delete_user(request, user_id):
    user = get_object_or_404(signin, id=user_id)
    if user.is_superuser:
        return JsonResponse({'error': 'Cannot delete superuser'}, status=403)
    name = user.name
    user.delete()
    return JsonResponse({'success': True, 'message': f'Deleted: {name}'})


# ─────────────────────────────────────────
# Admin: Proposals List
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_proposals(request):
    search = request.GET.get('search', '')
    status = request.GET.get('status', '')

    proposals = Proposal.objects.select_related('seller__user').order_by('-created_at')
    if search:
        proposals = proposals.filter(Q(title__icontains=search) | Q(seller__user__name__icontains=search))
    if status == 'active':
        proposals = proposals.filter(is_active=True)
    elif status == 'inactive':
        proposals = proposals.filter(is_active=False)

    return render(request, 'admin.html', {'section': 'proposals', 'proposals': proposals})


# ─────────────────────────────────────────
# Admin: Toggle Proposal Active (AJAX)
# ─────────────────────────────────────────
@login_required
@superuser_required
@require_POST
def admin_toggle_proposal(request, proposal_id):
    p = get_object_or_404(Proposal, id=proposal_id)
    p.is_active = not p.is_active
    p.save()
    return JsonResponse({'success': True, 'is_active': p.is_active, 'message': f"Proposal {'activated' if p.is_active else 'deactivated'}"})


# ─────────────────────────────────────────
# Admin: Delete Proposal (AJAX)
# ─────────────────────────────────────────
@login_required
@superuser_required
@require_POST
def admin_delete_proposal(request, proposal_id):
    p = get_object_or_404(Proposal, id=proposal_id)
    title = p.title
    p.delete()
    return JsonResponse({'success': True, 'message': f'Deleted: {title}'})


# ─────────────────────────────────────────
# Admin: Reviews List
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_reviews(request):
    reviews = Review.objects.select_related('client', 'seller').order_by('-created_at')
    avg     = reviews.aggregate(Avg('rating'))['rating__avg']
    return render(request, 'admin.html', {
        'section':    'reviews',
        'reviews':    reviews,
        'avg_rating': round(avg, 1) if avg else 0,
    })


# ─────────────────────────────────────────
# Admin: Delete Review (AJAX)
# ─────────────────────────────────────────
@login_required
@superuser_required
@require_POST
def admin_delete_review(request, review_id):
    get_object_or_404(Review, id=review_id).delete()
    return JsonResponse({'success': True, 'message': 'Review deleted'})


# ─────────────────────────────────────────
# Admin: Verifications
# (Profile photo nahi → unverified treat karo)
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_verifications(request):
    pending = Seller_Profile.objects.filter(
        profile_photo=''
    ).select_related('user').order_by('-user__date_joined')

    return render(request, 'admin.html', {'section': 'verifications', 'pending': pending})


# ─────────────────────────────────────────
# Admin: Messages / Conversations
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_messages_view(request):
    conversations = Conversation.objects.prefetch_related('participants', 'messages').order_by('-updated_at')[:50]

    conv_data = [{
        'conv':         conv,
        'participants': list(conv.participants.all()),
        'msg_count':    conv.messages.count(),
        'last_msg':     conv.messages.last(),
    } for conv in conversations]

    return render(request, 'admin.html', {
        'section':        'messages',
        'conv_data':      conv_data,
        'total_messages': Message.objects.count(),
        'total_convs':    Conversation.objects.count(),
    })


# ─────────────────────────────────────────
# Admin: Activity Logs
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_logs(request):
    return render(request, 'admin.html', {
        'section':           'logs',
        'recent_users':      signin.objects.order_by('-date_joined')[:8],
        'recent_reviews':    Review.objects.select_related('client', 'seller').order_by('-created_at')[:8],
        'recent_proposals':  Proposal.objects.select_related('seller__user').order_by('-created_at')[:8],
    })


# ─────────────────────────────────────────
# Admin: Stats JSON (for charts)
# ─────────────────────────────────────────
@login_required
@superuser_required
def admin_stats_json(request):
    today = timezone.now().date()

    daily_signups = [
        {'day': (today - timezone.timedelta(days=i)).strftime('%a'),
         'count': signin.objects.filter(date_joined__date=(today - timezone.timedelta(days=i))).count()}
        for i in range(6, -1, -1)
    ]

    workers  = signin.objects.filter(user_type='contractor').count()
    clients  = signin.objects.filter(user_type='client').count()
    inactive = signin.objects.filter(is_active=False).count()
    admins   = signin.objects.filter(is_superuser=True).count()

    return JsonResponse({
        'daily_signups':   daily_signups,
        'user_breakdown':  {'workers': workers, 'clients': clients, 'admins': admins, 'inactive': inactive},
        'total_users':     signin.objects.count(),
        'total_proposals': Proposal.objects.count(),
        'total_reviews':   Review.objects.count(),
        'avg_rating':      round(Review.objects.aggregate(Avg('rating'))['rating__avg'] or 0, 1),
    })


#-------------------------------------------------------
# otp
#-------------------------------------------------------

## views.py mein send_email_otp function mein
## send_mail ko replace karo is HTML email se:

from django.core.mail import EmailMultiAlternatives
from django.core.mail import send_mail
from django.conf import settings


def send_otp_email(user, otp):
    subject = 'ContractorHub — Email Verification Code'
    from_email = settings.DEFAULT_FROM_EMAIL
    to_email = user.email

    # Plain text fallback
    text_content = f'Your verification code is: {otp}\nExpires in 24 hours.'

    # HTML content
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f4f7fd;font-family:'Segoe UI',Arial,sans-serif;">

  <!-- Wrapper -->
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f7fd;padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;">

          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,#0a1628 0%,#1a3a6b 100%);border-radius:20px 20px 0 0;padding:35px 40px;text-align:center;position:relative;">
              <!-- Grid pattern overlay via border -->
              <div style="font-family:Georgia,serif;font-size:28px;font-weight:900;color:#ffffff;letter-spacing:-0.5px;">
                Contractor<span style="color:#c9903a;">Hub</span>
              </div>
              <div style="margin-top:8px;font-size:13px;color:rgba(255,255,255,0.55);letter-spacing:1px;text-transform:uppercase;">
                Email Verification
              </div>
            </td>
          </tr>

          <!-- BODY -->
          <tr>
            <td style="background:#ffffff;padding:40px 40px 30px;">

              <!-- Icon circle -->
              <div style="text-align:center;margin-bottom:24px;">
                <div style="display:inline-block;width:72px;height:72px;background:rgba(201,144,58,0.12);border:2px solid rgba(201,144,58,0.3);border-radius:50%;text-align:center;line-height:72px;font-size:28px;">
                  🔐
                </div>
              </div>

              <!-- Greeting -->
              <h2 style="margin:0 0 8px;font-family:Georgia,serif;font-size:22px;font-weight:700;color:#0a1628;text-align:center;">
                Salam, {user.name}!
              </h2>
              <p style="margin:0 0 28px;font-size:14px;color:#64748b;text-align:center;line-height:1.6;">
                Aapne ContractorHub pe email verify karne ki request ki hai.<br>
                Neeche diya gaya code use karein:
              </p>

              <!-- OTP Box -->
              <div style="background:linear-gradient(135deg,#0a1628,#1a3a6b);border-radius:16px;padding:28px 20px;text-align:center;margin-bottom:28px;">
                <div style="font-size:12px;color:rgba(255,255,255,0.5);letter-spacing:2px;text-transform:uppercase;margin-bottom:12px;">
                  Your Verification Code
                </div>
                <div style="font-family:'Courier New',monospace;font-size:42px;font-weight:900;color:#c9903a;letter-spacing:12px;line-height:1;">
                  {otp}
                </div>
                <div style="margin-top:12px;font-size:12px;color:rgba(255,255,255,0.4);">
                  ⏰ Expires in 24 hours
                </div>
              </div>

              <!-- Steps -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                <tr>
                  <td style="background:#f8f9fc;border-radius:12px;padding:20px 24px;">
                    <div style="font-size:12px;font-weight:700;color:#0a1628;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:14px;">
                      How to verify:
                    </div>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td style="padding:5px 0;">
                          <table cellpadding="0" cellspacing="0">
                            <tr>
                              <td style="width:26px;height:26px;background:#c9903a;border-radius:50%;text-align:center;vertical-align:middle;">
                                <span style="font-size:11px;font-weight:700;color:#0a1628;">1</span>
                              </td>
                              <td style="padding-left:12px;font-size:13px;color:#64748b;">
                                ContractorHub profile page pe jaayein
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;">
                          <table cellpadding="0" cellspacing="0">
                            <tr>
                              <td style="width:26px;height:26px;background:#c9903a;border-radius:50%;text-align:center;vertical-align:middle;">
                                <span style="font-size:11px;font-weight:700;color:#0a1628;">2</span>
                              </td>
                              <td style="padding-left:12px;font-size:13px;color:#64748b;">
                                Verification popup mein yeh code enter karein
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;">
                          <table cellpadding="0" cellspacing="0">
                            <tr>
                              <td style="width:26px;height:26px;background:#c9903a;border-radius:50%;text-align:center;vertical-align:middle;">
                                <span style="font-size:11px;font-weight:700;color:#0a1628;">3</span>
                              </td>
                              <td style="padding-left:12px;font-size:13px;color:#64748b;">
                                Done! Aapki email verify ho jaayegi ✅
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>

              <!-- Warning -->
              <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:10px;">
                <tr>
                  <td style="background:#fff8f0;border-left:3px solid #c9903a;border-radius:0 8px 8px 0;padding:12px 16px;">
                    <span style="font-size:12px;color:#92400e;">
                      ⚠️ <strong>Security Notice:</strong> Agar aap ne yeh request nahi ki toh is email ko ignore karein. Apna code kisi ke saath share na karein.
                    </span>
                  </td>
                </tr>
              </table>

            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#0a1628;border-radius:0 0 20px 20px;padding:24px 40px;text-align:center;">
              <div style="font-family:Georgia,serif;font-size:16px;font-weight:700;color:#ffffff;margin-bottom:6px;">
                Contractor<span style="color:#c9903a;">Hub</span>
              </div>
              <div style="font-size:11px;color:rgba(255,255,255,0.35);margin-bottom:12px;">
                Connecting skilled contractors with quality projects
              </div>
              <div style="font-size:10px;color:rgba(255,255,255,0.25);">
                © 2026 ContractorHub · Lahore, Pakistan<br>
                Yeh ek automated email hai — reply mat karein
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
"""

    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()


@login_required
def send_email_otp(request):
    user = request.user

    if user.is_email_verified:
        return JsonResponse({'success': False, 'message': 'Email already verified hai!'})

    import random, string
    otp = ''.join(random.choices(string.digits, k=6))

    user.email_otp = otp
    user.email_otp_created_at = timezone.now()
    user.save(update_fields=['email_otp', 'email_otp_created_at'])

    send_otp_email(user, otp)

    return JsonResponse({'success': True, 'message': 'OTP bhej di gayi hai!'})


@login_required
@require_POST
def verify_email_otp(request):
    """User ka OTP verify karo"""
    try:
        data = json.loads(request.body)
        otp_entered = data.get('otp', '').strip()
    except:
        return JsonResponse({'success': False, 'message': 'Invalid request'})

    user = request.user

    # Already verified?
    if user.is_email_verified:
        return JsonResponse({'success': False, 'message': 'Email pehle se verified hai!'})

    # OTP exist karta hai?
    if not user.email_otp:
        return JsonResponse({'success': False, 'message': 'Pehle OTP bhejein'})

    # 24 hour expiry check
    if user.email_otp_created_at:
        expiry = user.email_otp_created_at + timezone.timedelta(hours=24)
        if timezone.now() > expiry:
            return JsonResponse({'success': False, 'message': 'OTP expire ho gayi! Dobara bhejein.'})

    # OTP match karo
    if otp_entered == user.email_otp:
        user.is_email_verified = True
        user.email_otp = ''
        user.email_otp_created_at = None
        user.save(update_fields=['is_email_verified', 'email_otp', 'email_otp_created_at'])
        return JsonResponse({'success': True, 'message': 'Email verified ho gayi! ✅'})
    else:
        return JsonResponse({'success': False, 'message': 'Galat OTP! Dobara try karein.'})

#----------------------------------
#  firebase credential
#----------------------------------

# ─────────────────────────────────────────
# Phone OTP — Send
# ─────────────────────────────────────────


# ─────────────────────────────────────────
# Phone OTP — Verify
# ─────────────────────────────────────────
