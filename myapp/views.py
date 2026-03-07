from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib.auth import get_user_model, authenticate, login, logout
from .models import signin
from django.contrib import messages
from allauth.socialaccount.signals import pre_social_login
from django.dispatch import receiver
import re,os
import urllib.request
import urllib.error
from django.db.models import Count, Sum, Q, Avg
from django.utils import timezone
import json
from dotenv import load_dotenv
from django.contrib.auth.decorators import login_required
from django.db.models.functions import TruncDate
from .models import signin, Seller_Profile,Certificate,WorkExperience,Proposal,ProposalImpression,Message,Conversation,Client_Profile,Review

load_dotenv("env.env")

@login_required
def after_login(request):
    user = request.user
    
    # ── Agar user_type null hai — session sy lo ──
    if not user.user_type:
        user_type = request.session.get('user_type', 'client')
        user.user_type = user_type
        user.save()
    
    # ── user_type ke hisaab se redirect ──
    if user.user_type and user.user_type.lower() == 'contractor':
        return redirect('seller')
    else:
        return redirect('client')
    
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
    # Session mein jo user_type save tha — woh lo
    user_type = request.session.get('user_type', 'client')  # default client

    if sociallogin.is_existing:
        # Pehle se account hai — sirf tab update karo jab null ho
        user = sociallogin.user
        if not user.user_type:
            user.user_type = user_type
            user.save()
    else:
        # Naya Google user — user_type set karo
        sociallogin.user.user_type = user_type


# ─────────────────────────────────────────
# Landing Page — Role Select
# ─────────────────────────────────────────
def landing_page(request):
    if request.method == 'POST':
        user_type = request.POST.get('user_type')
        request.session['user_type'] = user_type  # session mein save — Google ke liye bhi kaam aayega
        return redirect(f'/signin/?user_type={user_type}')
    return render(request, 'landingpage.html')


# ─────────────────────────────────────────
# Signup Page
# ─────────────────────────────────────────
def login_page(request):
    context = {}
    user_type = request.GET.get('user_type')  # URL sy lo

    if request.method == 'POST':
        name          = request.POST.get("name")
        email         = request.POST.get("email")
        phone         = request.POST.get("phone")
        password      = request.POST.get("password")
        confirmed_pass = request.POST.get("confirm_password")

        # Form data repopulate karne ke liye
        context['form_data'] = {
            'name': name,
            'email': email,
            'phone': phone,
        }

        field_errors = {}

        # 1 — Empty fields check
        if not name or not email or not phone or not password or not confirmed_pass:
            messages.error(request, "All fields are required!")
            if not name:          field_errors['name']             = "Name is required"
            if not email:         field_errors['email']            = "Email is required"
            if not phone:         field_errors['phone']            = "Phone is required"
            if not password:      field_errors['password']         = "Password is required"
            if not confirmed_pass: field_errors['confirm_password'] = "Please confirm your password"

        # 2 — Password match check
        elif password != confirmed_pass:
            messages.error(request, "Passwords do not match!")
            field_errors['password']         = "Passwords do not match"
            field_errors['confirm_password'] = "Passwords do not match"

        else:
            # 3 — Strong password check
            password_errors = validate_strong_password(password)
            if password_errors:
                for error in password_errors:
                    messages.error(request, error)
                field_errors['password'] = "Password is not strong enough"

            # 4 — Phone digits only
            elif phone and not phone.isdigit():
                messages.error(request, "Phone number should contain only digits!")
                field_errors['phone'] = "Only digits allowed"

            # 5 — Email already exists
            elif signin.objects.filter(email=email).exists():
                messages.error(request, "Email already exists!")
                field_errors['email'] = "This email is already registered"

            # 6 — user banao
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

                    # user_type ke hisaab sy redirect
                    if user_type and user_type.lower() == 'contractor':
                        return redirect('seller')
                    else:
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
                    else:
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
    return render(request, 'home.html')


# ─────────────────────────────────────────
# Loader
# ─────────────────────────────────────────
def loader(request):
    return render(request, 'loader.html')


# ─────────────────────────────────────────
# Client Dashboard
# ─────────────────────────────────────────

@login_required
def client_page(request):
    # Login check
    if not request.user.is_authenticated:
        return redirect('landing_page')
    
    # user_type null hai — role select karo
    if not request.user.user_type:
        return redirect('landing_page')
    
    # Agar contractor hai to seller page pe bhejo
    if request.user.user_type.lower() == 'contractor':
        return redirect('seller')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    category = request.GET.get('category', '')
    
    # Available workers fetch karo (sellers)
    workers = Seller_Profile.objects.filter(
    is_available=True,
    user__user_type='contractor'  # ✅ only actual contractors
)
    
    if search_query:
        workers = workers.filter(
            Q(user__name__icontains=search_query) |
            Q(skills__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(title__icontains=search_query)
        )
    
    if category:
        workers = workers.filter(skills__icontains=category)
    
    # Total unread messages
    total_unread = 0
    conversations = Conversation.objects.filter(participants=request.user)
    for conv in conversations:
        total_unread += conv.messages.filter(is_read=False).exclude(sender=request.user).count()
    
    context = {
        'workers': workers,
        'search_query': search_query,
        'category': category,
        'total_unread': total_unread,
        'notifications_count': 0,  # Baad mein implement karo
    }
    return render(request, 'client.html', context)


# ─────────────────────────────────────────
# Client profile
# ─────────────────────────────────────────


@login_required
def client_profile(request):
    # Login check
    if not request.user.is_authenticated:
        return redirect('landing_page')
    
    # Agar contractor hai to seller profile pe bhejo
    if request.user.user_type and request.user.user_type.lower() == 'contractor':
        return redirect('seller_profile')
    
    # Client profile get or create karo
    try:
        client_profile = Client_Profile.objects.get(user=request.user)
    except Client_Profile.DoesNotExist:
        client_profile = Client_Profile.objects.create(user=request.user)
    
    if request.method == 'POST':
        # City and language update karo
        city = request.POST.get('city', '')
        language = request.POST.get('language', '')
        
        client_profile.city = city
        client_profile.language = language
        
        # Profile photo upload
        if request.FILES.get('profile_photo'):
            client_profile.profile_photo = request.FILES['profile_photo']
        
        client_profile.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('client_profile')
    
    # Profile complete percentage calculate karo
    profile_complete = 50  # Base: name + email
    if client_profile.city:
        profile_complete += 25
    if client_profile.language:
        profile_complete += 25
    my_reviews = Review.objects.filter(
        seller=request.user
    ).select_related('client').order_by('-created_at')
    avg_rating = None
    if my_reviews.exists():
        avg = my_reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)
    # Total unread messages
    total_unread = 0
    conversations = Conversation.objects.filter(participants=request.user)
    for conv in conversations:
        total_unread += conv.messages.filter(is_read=False).exclude(sender=request.user).count()
    
    context = {
        'user': request.user,
        'client_profile': client_profile,
        'profile_complete': profile_complete,
        'total_unread': total_unread,
        'my_reviews': my_reviews,  
        'avg_rating': avg_rating, 
    }
    return render(request, 'client_profile.html', context)# ─────────────────────────────────────────
# Seller / Contractor Dashboard
# ─────────────────────────────────────────
@login_required
def seller_page(request):
    if not request.user.is_authenticated:
        return redirect('landing_page')
    
    if not request.user.user_type:
        return redirect('landing_page')
    
    if request.user.user_type.lower() == 'client':
        return redirect('client')
    # Get or create seller profile
    profile, created = Seller_Profile.objects.get_or_create(user=request.user)
    
    # Active proposals
    active_proposals = Proposal.objects.filter(seller=profile, is_active=True)
    active_bids_count = active_proposals.count()

    # Level name mapping
    level_names = {
        1: "Beginner", 2: "Apprentice", 3: "Journeyman", 
        4: "Skilled Worker", 5: "Craftsman", 6: "Expert",
        7: "Specialist", 8: "Master", 9: "Grand Master", 10: "Legend"
    }
    level_name = level_names.get(profile.level, f"Level {profile.level}")
    
    # XP calculation based on level
    current_xp = profile.level * 800 + 200
    next_level_xp = (profile.level + 1) * 1000
    xp_percentage = int((current_xp / next_level_xp) * 100)
    
    # Recent proposals — real data only
    recent_proposals = Proposal.objects.filter(
        seller=profile
    ).order_by('-created_at')[:3]
    
    context = {
        'profile': profile,
        'active_bids_count': active_bids_count,
        'active_projects_count': active_bids_count,
        'active_projects_change': 0,
        'pending_proposals_count': active_bids_count,
        'pending_proposals_change': 0,
        'level_name': level_name,
        'current_xp': current_xp,
        'next_level_xp': next_level_xp,
        'xp_percentage': xp_percentage,
        'recent_proposals': recent_proposals,
    }
    
    return render(request, 'seller.html', context)

# ─────────────────────────────────────────
# Admin Panel
# ─────────────────────────────────────────
def admin(request):
    return render(request, 'admin.html')




@login_required
def seller_profile_page(request):
    profile, created = Seller_Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':

        if request.POST.get('availability_only'):
            profile.is_available = request.POST.get('is_available') == 'on'
            profile.save()
            return redirect('seller_profile')

        name = request.POST.get('name', '').strip()
        if name:
            request.user.name = name
            request.user.save()

        profile.title        = request.POST.get('title', '')
        profile.city         = request.POST.get('city', '')
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

    # ✅ POST block ke BAHAR — yahan rakho
    reviews = Review.objects.filter(seller=request.user).select_related('client').order_by('-created_at')
    reviews_count = reviews.count()
    avg_rating = None
    if reviews_count:
        avg = reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)
    jobs_count = Proposal.objects.filter(seller=profile).count()

    context = {
        'user': request.user,
        'profile': profile,
        'experiences': profile.experiences.all(),
        'certificates': profile.certificates.all(),
        'reviews': reviews,
        'avg_rating': avg_rating,
        'reviews_count': reviews_count,
        'jobs_count': jobs_count,
    }
    return render(request, 'profile_seller.html', context)
@login_required
def add_experience(request):
    if request.method == 'POST':
        profile = request.user.seller_profile

        # ✅ Month to date convert karo
        start_raw = request.POST.get('start_date')  # "2026-01"
        end_raw   = request.POST.get('end_date')    # "2026-03" ya ""

        start_date = f"{start_raw}-01" if start_raw else None
        end_date   = f"{end_raw}-01"   if end_raw else None

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
    
@login_required
def create_proposal(request):
    profile = request.user.seller_profile
    if request.method == 'POST':
        Proposal.objects.create(
            seller        = profile,
            title         = request.POST.get('title'),
            description   = request.POST.get('description', ''),
            search_tag    = request.POST.get('search_tag', ''),
            work_type     = request.POST.get('work_type'),
            base_price    = request.POST.get('base_price'),
            delivery_time = request.POST.get('delivery_time', ''),
            portfolio_image = request.FILES.get('portfolio_image'),
            doc_portfolio = request.FILES.get('doc_portfolio'),
            video_intro = request.FILES.get('video_intro'),
            is_active     = request.POST.get('is_active') == 'true',
        )
        messages.success(request, "Proposal published successfully!")
        return redirect('seller_profile')  # baad mein banayenge

    context = {'user': request.user, 'profile': profile}
    return render(request, 'proposal.html', context)


@login_required
def my_proposals(request):
    profile = request.user.seller_profile
    proposals = Proposal.objects.filter(seller=profile).order_by('-created_at')

    total_proposals  = proposals.count()
    active_count     = proposals.filter(is_active=True).count()
    total_impressions = ProposalImpression.objects.filter(proposal__seller=profile).count()

    # ── proposals ko JSON mein convert karo (modal ke liye) ──
    proposals_list = []
    for p in proposals:
        proposals_list.append({
            'id':            p.id,
            'title':         p.title,
            'work_type':     p.work_type,
            'base_price':    str(p.base_price),
            'delivery_time': p.delivery_time,
            'search_tag':    p.search_tag,
            'is_active':     p.is_active,
            'created_at':    p.created_at.strftime('%b %d, %Y'),
        })

    # ── impressions per proposal (daily breakdown) ──
    impressions_dict = {}
    today = timezone.now().date()

    for p in proposals:
        imp_qs = ProposalImpression.objects.filter(proposal=p)

        # Daily counts
        daily_qs = (
            imp_qs
            .annotate(day=TruncDate('viewed_at'))
            .values('day')
            .annotate(count=Count('id'))
        )
        daily = {str(row['day']): row['count'] for row in daily_qs}

        # Period totals
        total  = imp_qs.count()
        t_today = imp_qs.filter(viewed_at__date=today).count()
        week   = imp_qs.filter(viewed_at__date__gte=today - timezone.timedelta(days=7)).count()
        month  = imp_qs.filter(viewed_at__date__gte=today - timezone.timedelta(days=30)).count()

        impressions_dict[p.id] = {
            'total': total,
            'today': t_today,
            'week':  week,
            'month': month,
            'daily': daily,
        }

    context = {
        'profile':          profile,
        'proposals':        proposals,
        'total_proposals':  total_proposals,
        'active_count':     active_count,
        'total_impressions': total_impressions,
        'proposals_json':   json.dumps(proposals_list),
        'impressions_json': json.dumps(impressions_dict),
    }
    return render(request, 'active_work.html', context)


def faqs(requests):
    return render(requests,'faqs.html')


#---------------
#      messages
#---------------
@login_required
def messages_page(request):
    user = request.user

    # Sari conversations latest first
    conversations = Conversation.objects.filter(
        participants=user
    ).prefetch_related('participants', 'messages').order_by('-updated_at')

    # Har conversation ka extra data
    conv_data = []
    for conv in conversations:
        other_user = conv.get_other_user(user)
        if not other_user:
            continue

        # Other user ki profile photo
        other_photo = None
        try:
            sp = other_user.seller_profile
            if sp.profile_photo:
                other_photo = sp.profile_photo.url
        except:
            pass

        last_msg = conv.messages.last()
        unread   = conv.get_unread_count(user)

        conv_data.append({
            'id':                       conv.id,
            'other_user':               other_user,
            'other_user_profile_photo': other_photo,
            'last_message':             last_msg,
            'last_message_time':        conv.updated_at,
            'unread_count':             unread,
            'is_online':                False,
            'last_seen':                conv.updated_at,
        })

    # Active conversation — URL se ?conv=ID
    active_conv_data = None
    messages_list    = []
    last_message_id  = 0 
    conv_id          = request.GET.get('conv')

    if conv_id:
        try:
            active_conv_obj = Conversation.objects.get(
                id=conv_id,
                participants=user
            )
            other_user = active_conv_obj.get_other_user(user)

            other_photo = None
            try:
                sp = other_user.seller_profile
                if sp.profile_photo:
                    other_photo = sp.profile_photo.url
            except:
                pass

            active_conv_data = {
                'id':                       active_conv_obj.id,
                'other_user':               other_user,
                'other_user_profile_photo': other_photo,
                'is_online':                False,
                'last_seen':                active_conv_obj.updated_at,
            }

            messages_list = active_conv_obj.messages.select_related(
                'sender', 'proposal'
            ).all()
            last_message_id = 0
            if messages_list.exists():
                last_message_id = messages_list.last().id
            # Unread messages mark as read
            active_conv_obj.messages.filter(
                is_read=False
            ).exclude(sender=user).update(is_read=True)

        except Conversation.DoesNotExist:
            pass

    # Total unread count — bell icon ke liye
    total_unread = sum(c['unread_count'] for c in conv_data)

    # Seller profile
    try:
        profile = user.seller_profile
    except:
        profile = None

    # My proposals — attach feature ke liye
    my_proposals = []
    if profile:
        my_proposals = Proposal.objects.filter(
            seller=profile,
            is_active=True
        )

    context = {
        'profile':       profile,
        'conversations': conv_data,
        'active_conv':   active_conv_data,
        'messages':      messages_list,
        'total_unread':  total_unread,
        'my_proposals':  my_proposals,
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

    # ── Contractor check ──
    # Contractor sirf reply kar sakta hai
    # Agar conv mein koi message nahi aur contractor pehla message karna chahta hai — block
    if request.user.user_type == 'contractor' and not request.user.is_superuser:
        first_msg = conv.messages.first()
        if not first_msg:
            return redirect('messages_page')

    content = request.POST.get('content', '').strip()
    if not content:
        return redirect(f"/messages/?conv={conv_id}")

    # Proposal attach
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

    # updated_at refresh karo — sidebar mein latest dikhega
    conv.updated_at = timezone.now()
    conv.save()

    return redirect(f"/messages/?conv={conv_id}")


# ─────────────────────────────────────────
# Check New Messages — JS polling (5 sec)
# ─────────────────────────────────────────
@login_required
def check_new_messages(request, conv_id):
    try:
        conv     = Conversation.objects.get(id=conv_id, participants=request.user)
        last_id  = int(request.GET.get('last_id', 0))

        new_msgs = conv.messages.filter(id__gt=last_id).exclude(sender=request.user)
        has_new  = new_msgs.exists()

        latest   = conv.messages.last()
        latest_id = latest.id if latest else 0

        return JsonResponse({
            'has_new':   has_new,
            'latest_id': latest_id,
            'is_typing': False,
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'has_new': False, 'latest_id': 0, 'is_typing': False})
    except Exception as e:
        return JsonResponse({'has_new': False, 'latest_id': 0, 'is_typing': False})


# ─────────────────────────────────────────
# View profile
# ─────────────────────────────────────────


@login_required
def view_profile(request, user_id):
    target_user = get_object_or_404(signin, id=user_id)
    
    seller_profile = None
    client_profile = None
    experiences = []
    certificates = []
    active_proposals = []
    level_name = "Beginner"

    if target_user.user_type and target_user.user_type.lower() == 'contractor':
        seller_profile = get_object_or_404(Seller_Profile, user=target_user)
        experiences    = seller_profile.experiences.all()
        certificates   = seller_profile.certificates.all()
        active_proposals = seller_profile.proposals.filter(is_active=True)
        level_map = {1:'Beginner', 2:'Intermediate', 3:'Expert'}
        level_name = level_map.get(seller_profile.level, 'Beginner')
    else:
        try:
            client_profile = Client_Profile.objects.get(user=target_user)
        except:
            client_profile = None

    # ── Reviews fetch karo ──
    reviews = Review.objects.filter(
        seller=target_user
    ).select_related('client').order_by('-created_at')

    # ── Current user ka apna review (agar pehle diya ho) ──
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
    # ── Sirf client ya admin start kar sakta hai ──
    if request.user.user_type == 'contractor' and not request.user.is_superuser:
        return redirect('messages_page')

    seller_user = get_object_or_404(signin, id=seller_user_id)

    # Apne aap ko message nahi kar sakte
    if seller_user == request.user:
        return redirect('messages_page')

    # Already conversation hai?
    conv = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=seller_user
    ).first()

    # Nahi hai toh naya banao
    if not conv:
        conv = Conversation.objects.create(started_by=request.user)
        conv.participants.add(request.user, seller_user)

    return redirect(f"/messages/?conv={conv.id}")

def privacy(requests):
    return render(requests,'privacy.html')

def about_us(requests):
    return render(requests,'about_us.html')


def logout_view(request):
    logout(request)
    return redirect('landing_page')

# ─────────────────────────────────────────
# Review submittion
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

    # Update avg_rating if target is contractor
    if target_user.user_type.lower() == 'contractor':
        from django.db.models import Avg
        avg = Review.objects.filter(seller=target_user).aggregate(Avg('rating'))['rating__avg']
        Seller_Profile.objects.filter(user=target_user).update(avg_rating=round(avg, 1))

    return redirect('view_profile', user_id=user_id)


#-------------------
# Show seller
#-------------------

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
        first_proposal = w.proposals.filter(is_active=True).first()

        price          = str(first_proposal.base_price)             if first_proposal else ''
        gig_title      = first_proposal.title                       if first_proposal else ''
        proposal_desc  = (first_proposal.description or '')[:120]   if first_proposal else ''
        proposal_image = first_proposal.portfolio_image.url         if first_proposal and first_proposal.portfolio_image else ''

        workers_data.append({
            'id':             w.user.id,
            'name':           w.user.name or '',
            'title':          w.title or '',
            'skills':         w.skills or '',
            'city':           w.city or '',
            'rating':         float(w.avg_rating) if w.avg_rating else 4.5,
            'price':          price,
            'photo':          w.profile_photo.url if w.profile_photo else '',
            'profile_url':    f'/view_profile/{w.user.id}/',
            'message_url':    f'/start_conversation/{w.user.id}/',
            'gig_title':      gig_title,
            'proposal_desc':  proposal_desc,
            'proposal_image': proposal_image,
        })

    total_unread = 0
    for conv in Conversation.objects.filter(participants=request.user):
        total_unread += conv.messages.filter(is_read=False).exclude(sender=request.user).count()

    return render(request, 'show_seller.html', {
        'workers_json': json.dumps(workers_data, ensure_ascii=False),
        'total_unread': total_unread,
    })

# ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
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
# HELPER: Build context for AI
# ─────────────────────────────────────────

def _build_client_context(request):
    """Fetch all available workers from DB for client AI recommendations."""
    from .models import Seller_Profile

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
            'profile_url': f'/view_profile/{w.user.id}/',
            'about':       (w.about or '')[:200],  # truncate for token limit
        })

    return {
        'user_name':       request.user.name or 'Client',
        'user_city':       '',  # can be added if client_profile has city
        'available_workers': workers_data,
        'total_workers':   len(workers_data),
    }


def _build_seller_context(request):
    """Fetch seller's own profile data for AI coaching."""
    from .models import Seller_Profile, Proposal, Review
    from django.db.models import Avg

    try:
        profile = request.user.seller_profile
    except:
        return {'user_name': request.user.name or 'Contractor'}

    # Reviews summary
    reviews = Review.objects.filter(seller=request.user)
    avg_rating = None
    if reviews.exists():
        avg = reviews.aggregate(Avg('rating'))['rating__avg']
        avg_rating = round(avg, 1)

    # Active proposals
    proposals = Proposal.objects.filter(seller=profile, is_active=True)
    proposals_data = [{
        'title':         p.title,
        'description':   (p.description or '')[:150],
        'price':         str(p.base_price),
        'work_type':     p.work_type,
        'has_image':     bool(p.portfolio_image),
        'has_video':     bool(p.video_intro),
        'has_document':  bool(p.doc_portfolio),
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
# HELPER: Call Anthropic API
# ─────────────────────────────────────────

def _call_groq(system_prompt, messages_history, api_key):
    """
    Call Groq using official SDK — same as ARIA project.
    Returns (response_text, error_message)
    """
    try:
        from groq import Groq
        client = Groq(api_key=api_key)

        messages = [{"role": "system", "content": system_prompt}] + messages_history

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=800,
            temperature=0.7,
        )
        text = response.choices[0].message.content
        return text.strip(), None

    except Exception as e:
        return None, str(e)


# ─────────────────────────────────────────
# VIEW: /ai-context/ — load initial context
# ─────────────────────────────────────────

@login_required
def ai_context(request):
    """
    Returns the user's role + basic context data for the frontend bubble.
    Called once when the bubble opens.
    """
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

    return JsonResponse({
        'role':    role,
        'context': ctx,
        'welcome': welcome,
    })


# ─────────────────────────────────────────
# VIEW: /ai-chat/ — main chat endpoint
# ─────────────────────────────────────────

@login_required
@require_POST
def ai_chat(request):
    """
    POST body (JSON):
    {
        "message": "user's message",
        "history": [{"role": "user"|"assistant", "content": "..."}]
    }

    Returns:
    {
        "reply": "AI response text",
        "error": null | "error message"
    }
    """
    from django.conf import settings

    # ── Parse request ──
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'reply': '', 'error': 'Invalid JSON'}, status=400)

    user_message = body.get('message', '').strip()
    history      = body.get('history', [])  # list of {role, content}

    if not user_message:
        return JsonResponse({'reply': '', 'error': 'Empty message'}, status=400)

    # ── Determine role ──
    user = request.user
    is_seller = user.user_type and user.user_type.lower() == 'contractor'

    # ── Build context & system prompt ──
    if is_seller:
        ctx           = _build_seller_context(request)
        system_prompt = SELLER_SYSTEM_PROMPT + f"\n\nCurrent seller profile data:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"
    else:
        ctx           = _build_client_context(request)
        system_prompt = CLIENT_SYSTEM_PROMPT + f"\n\nAvailable workers on platform right now:\n{json.dumps(ctx, ensure_ascii=False, indent=2)}"

    # ── Build messages array (history + new message) ──
    # Keep last 8 turns to stay within token limits
    recent_history = history[-8:] if len(history) > 8 else history
    messages_payload = recent_history + [{"role": "user", "content": user_message}]

    # ── Get API key from Django settings ──
    api_key = getattr(settings, 'GROQ_API_KEY', None) or os.environ.get('GROQ_API') or os.environ.get('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({
            'reply': '',
            'error': 'GROQ_API_KEY not configured in settings.py'
        }, status=500)

    # ── Call Claude ──
    reply, error = _call_groq(system_prompt, messages_payload, api_key)

    if error:
        return JsonResponse({'reply': '', 'error': error}, status=500)

    return JsonResponse({'reply': reply, 'error': None})
# ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────