from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.text import slugify

#custom user create
class user_manager(BaseUserManager):
    def create_user(self,email,name,password=None,**extra_fields):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)

        if not extra_fields.get('username'):
            base_username = slugify(email.split('@')[0])
            username = base_username
            counter = 1
            
            while self.model.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
                
            extra_fields['username'] = username

        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, password=None, **extra_fields):
        # ✅ CORRECTED: extra_fields ko override mat karo, update karo
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        # ✅ CORRECTED: extra_fields pass karo
        return self.create_user(email=email, name=name, password=password, **extra_fields)
    
#user signin
class signin(AbstractUser):
    name = models.CharField(max_length=100,null=True)
    email = models.EmailField(max_length=100,unique=True)
    username = models.CharField(max_length=100,null=True,blank=True,unique=True)
    phone = models.CharField(max_length=12,blank=True)
    profile_image = models.URLField(max_length=500, null=True, blank=True)
    user_type     = models.CharField(max_length=20, null=True, blank=True)
    
    objects = user_manager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    def __str__(self):
        return self.email
    
class Seller_Profile(models.Model):
    user = models.OneToOneField(signin, on_delete=models.CASCADE, related_name='seller_profile')
    cover_photo = models.ImageField(upload_to='covers/', blank=True, null=True)
    profile_photo = models.ImageField(upload_to='profiles/', blank=True, null=True)
    city = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=20, blank=True)
    skills = models.TextField(blank=True)  # Comma separated: "Plumbing,Electrical,Construction"
    title = models.CharField(max_length=100, blank=True)  # "Master Contractor"
    about = models.TextField(blank=True)  # Bio
    is_available = models.BooleanField(default=True)  # Available toggle
    avg_rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    
    # Level system (optional)
    level = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name or self.user.email} - Seller"

    def get_skills_list(self):
        """Skills ko list mein convert karo"""
        if self.skills:
            return [s.strip() for s in self.skills.split(',')]
        return []

class WorkExperience(models.Model):
    seller = models.ForeignKey(Seller_Profile, on_delete=models.CASCADE, related_name='experiences')
    job_title = models.CharField(max_length=100)
    company = models.CharField(max_length=100)
    city = models.CharField(max_length=50, blank=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # null = current job
    is_current = models.BooleanField(default=False)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']

class Certificate(models.Model):
    seller = models.ForeignKey(Seller_Profile, on_delete=models.CASCADE, related_name='certificates')
    title = models.CharField(max_length=100)
    file = models.FileField(upload_to='certificates/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Proposal(models.Model):  # ✅ typo fix — Propsal → Proposal
    seller      = models.ForeignKey(Seller_Profile, on_delete=models.CASCADE, related_name='proposals')
    title       = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    search_tag  = models.CharField(max_length=100)
    work_type   = models.CharField(max_length=100)
    base_price  = models.DecimalField(max_digits=10, decimal_places=2)  # ✅ price ke liye
    delivery_time   = models.CharField(max_length=50, blank=True)
    is_active       = models.BooleanField(default=True)
    portfolio_image = models.ImageField(upload_to='proposals/images/', blank=True, null=True)
    doc_portfolio   = models.FileField(upload_to='proposals/docs/', blank=True, null=True)
    video_intro = models.FileField(upload_to='proposals/videos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

class ProposalImpression(models.Model):
    """Har baar koi proposal dekhe — ek record"""
    proposal   = models.ForeignKey(Proposal, on_delete=models.CASCADE, related_name='impressions')
    viewed_at  = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.proposal.title} — {self.viewed_at.date()}"
    

class Conversation(models.Model):
    participants = models.ManyToManyField(signin, related_name='conversations')
    started_by   = models.ForeignKey(signin, on_delete=models.SET_NULL, null=True, blank=True, related_name='started_conversations')  # ← sirf yeh add karo
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def get_other_user(self, current_user):
        return self.participants.exclude(id=current_user.id).first()

    def get_unread_count(self, current_user):
        return self.messages.filter(is_read=False).exclude(sender=current_user).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender       = models.ForeignKey(signin, on_delete=models.CASCADE, related_name='sent_messages')
    content      = models.TextField()
    proposal     = models.ForeignKey(Proposal, null=True, blank=True, on_delete=models.SET_NULL)
    is_read      = models.BooleanField(default=False)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Client_Profile(models.Model):
    user = models.OneToOneField(signin, on_delete=models.CASCADE, related_name='client_profile')
    city = models.CharField(max_length=50, blank=True)
    language = models.CharField(max_length=20, blank=True)
    company_name = models.CharField(max_length=100, blank=True)
    profile_photo = models.ImageField(upload_to='client_profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name or self.user.email} - Client"
    

class Review(models.Model):
    seller    = models.ForeignKey(signin, on_delete=models.CASCADE, related_name='reviews_received')
    client    = models.ForeignKey(signin, on_delete=models.CASCADE, related_name='reviews_given')
    rating    = models.IntegerField()  # 1-5
    comment   = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('seller', 'client')  # one review per client per seller