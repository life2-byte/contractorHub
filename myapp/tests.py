from django.test import TestCase, Client
from django.urls import reverse
from .models import signin, Seller_Profile, Client_Profile, Proposal, Review
from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp


# ─────────────────────────────────────────
# HELPER: Google/Facebook app test DB mein banana
# (allauth ko chahiye warna login.html crash karta hai)
# ─────────────────────────────────────────
def create_social_apps():
    site = Site.objects.get_current()

    google_app, _ = SocialApp.objects.get_or_create(
        provider='google',
        defaults={'name': 'Google', 'client_id': 'test', 'secret': 'test'}
    )
    google_app.sites.add(site)

    facebook_app, _ = SocialApp.objects.get_or_create(
        provider='facebook',
        defaults={'name': 'Facebook', 'client_id': 'test', 'secret': 'test'}
    )
    facebook_app.sites.add(site)


# ─────────────────────────────────────────
# 1. USER MODEL TESTS (Unit Tests)
# ─────────────────────────────────────────
class UserModelTest(TestCase):

    def test_create_client_user(self):
        """Normal client user bana sakte hain"""
        user = signin.objects.create_user(
            email='client@test.com',
            name='Test Client',
            password='Test@1234',
            user_type='client'
        )
        self.assertEqual(user.email, 'client@test.com')
        self.assertEqual(user.user_type, 'client')
        self.assertTrue(user.is_active)

    def test_create_contractor_user(self):
        """Contractor user bana sakte hain"""
        user = signin.objects.create_user(
            email='contractor@test.com',
            name='Test Contractor',
            password='Test@1234',
            user_type='contractor'
        )
        self.assertEqual(user.user_type, 'contractor')

    def test_email_is_unique(self):
        """Same email se 2 accounts nahi ban sakte"""
        signin.objects.create_user(
            email='same@test.com',
            name='User One',
            password='Test@1234'
        )
        with self.assertRaises(Exception):
            signin.objects.create_user(
                email='same@test.com',
                name='User Two',
                password='Test@1234'
            )

    def test_username_auto_generated(self):
        """Username automatically email se banta hai"""
        user = signin.objects.create_user(
            email='ali.hassan@test.com',
            name='Ali Hassan',
            password='Test@1234'
        )
        self.assertIsNotNone(user.username)
        self.assertIn('ali', user.username)

    def test_user_str(self):
        """User ka string representation email hona chahiye"""
        user = signin.objects.create_user(
            email='str@test.com',
            name='Str Test',
            password='Test@1234'
        )
        self.assertEqual(str(user), 'str@test.com')


# ─────────────────────────────────────────
# 2. PASSWORD VALIDATION TESTS (Unit Tests)
# ─────────────────────────────────────────
class PasswordValidationTest(TestCase):

    def setUp(self):
        from myapp.views import validate_strong_password
        self.validate = validate_strong_password

    def test_strong_password_passes(self):
        """Strong password mein koi error nahi aana chahiye"""
        errors = self.validate('StrongPass@123')
        self.assertEqual(len(errors), 0)

    def test_short_password_fails(self):
        """8 se kam characters wala password fail hona chahiye"""
        errors = self.validate('Ab@1')
        self.assertTrue(any('8' in e for e in errors))

    def test_no_uppercase_fails(self):
        """Bina uppercase ke password fail hona chahiye"""
        errors = self.validate('weakpass@123')
        self.assertTrue(any('UPPERCASE' in e or 'uppercase' in e.lower() for e in errors))

    def test_no_special_char_fails(self):
        """Bina special character ke password fail hona chahiye"""
        errors = self.validate('WeakPass123')
        self.assertTrue(len(errors) > 0)

    def test_no_number_fails(self):
        """Bina number ke password fail hona chahiye"""
        errors = self.validate('WeakPass@abc')
        self.assertTrue(len(errors) > 0)


# ─────────────────────────────────────────
# 3. PAGE LOAD TESTS (System Tests)
# ─────────────────────────────────────────
class PageLoadTest(TestCase):

    def setUp(self):
        self.browser = Client()
        create_social_apps()  # Google/Facebook fix

    def test_landing_page_loads(self):
        """Landing page khulni chahiye"""
        response = self.browser.get(reverse('landing_page'))
        self.assertEqual(response.status_code, 200)

    def test_signin_page_loads(self):
        """Signin page khulni chahiye"""
        response = self.browser.get(reverse('signin'))
        self.assertEqual(response.status_code, 200)

    def test_home_page_loads(self):
        """Home page khulni chahiye"""
        response = self.browser.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

    def test_faqs_page_loads(self):
        """FAQs page khulni chahiye"""
        response = self.browser.get(reverse('faqs'))
        self.assertEqual(response.status_code, 200)

    def test_privacy_page_loads(self):
        """Privacy page khulni chahiye"""
        response = self.browser.get(reverse('privacy'))
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────
# 4. LOGIN / SIGNUP TESTS (Integration Tests)
# ─────────────────────────────────────────
class AuthTest(TestCase):

    def setUp(self):
        self.browser = Client()
        create_social_apps()  # Google/Facebook fix
        self.client_user = signin.objects.create_user(
            email='client@test.com',
            name='Client User',
            password='Test@1234',
            user_type='client'
        )
        self.contractor_user = signin.objects.create_user(
            email='contractor@test.com',
            name='Contractor User',
            password='Test@1234',
            user_type='contractor'
        )

    def test_valid_login_redirects(self):
        """Sahi email/password se login ho jaata hai"""
        response = self.browser.post(reverse('signin'), {
            'email': 'client@test.com',
            'password': 'Test@1234'
        })
        self.assertEqual(response.status_code, 302)

    def test_invalid_login_fails(self):
        """Galat password se login nahi hona chahiye"""
        response = self.browser.post(reverse('signin'), {
            'email': 'client@test.com',
            'password': 'WrongPass@999'
        })
        self.assertEqual(response.status_code, 200)

    def test_client_redirects_to_client_dashboard(self):
        """Client login ke baad client dashboard pe jaata hai"""
        self.browser.login(username='client@test.com', password='Test@1234')
        response = self.browser.get(reverse('after_login'))
        self.assertRedirects(response, reverse('client'))

    def test_contractor_redirects_to_seller_dashboard(self):
        """Contractor login ke baad seller dashboard pe jaata hai"""
        self.browser.login(username='contractor@test.com', password='Test@1234')
        response = self.browser.get(reverse('after_login'))
        self.assertRedirects(response, reverse('seller'))

    def test_logout_works(self):
        """Logout ke baad protected pages accessible nahi honi chahiye"""
        self.browser.login(username='client@test.com', password='Test@1234')
        self.browser.get(reverse('logout'))
        response = self.browser.get(reverse('client'))
        self.assertEqual(response.status_code, 302)


# ─────────────────────────────────────────
# 5. AUTHORIZATION TESTS (Security Tests)
# ─────────────────────────────────────────
class AuthorizationTest(TestCase):

    def setUp(self):
        self.browser = Client()
        self.normal_user = signin.objects.create_user(
            email='normal@test.com',
            name='Normal User',
            password='Test@1234',
            user_type='client'
        )

    def test_unauthenticated_user_cannot_access_client_page(self):
        """Bina login ke client page nahi khulni chahiye"""
        response = self.browser.get(reverse('client'))
        self.assertEqual(response.status_code, 302)

    def test_unauthenticated_user_cannot_access_seller_page(self):
        """Bina login ke seller page nahi khulni chahiye"""
        response = self.browser.get(reverse('seller'))
        self.assertEqual(response.status_code, 302)

    def test_normal_user_cannot_access_admin(self):
        """Normal user admin panel access nahi kar sakta"""
        self.browser.login(username='normal@test.com', password='Test@1234')
        response = self.browser.get(reverse('myadmin'))
        self.assertNotEqual(response.status_code, 200)

    def test_superuser_can_access_admin(self):
        """Superuser admin panel access kar sakta hai"""
        signin.objects.create_superuser(
            email='admin@test.com',
            name='Admin User',
            password='Admin@1234'
        )
        self.browser.login(username='admin@test.com', password='Admin@1234')
        response = self.browser.get(reverse('myadmin'))
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────
# 6. SELLER PROFILE TESTS (Integration Tests)
# ─────────────────────────────────────────
class SellerProfileTest(TestCase):

    def setUp(self):
        self.browser = Client()
        self.seller = signin.objects.create_user(
            email='seller@test.com',
            name='Seller User',
            password='Test@1234',
            user_type='contractor'
        )
        self.profile = Seller_Profile.objects.create(
            user=self.seller,
            title='Expert Plumber',
            city='Lahore',
            skills='Plumbing,Electrical',
        )

    def test_seller_profile_created(self):
        """Seller profile theek se banta hai"""
        self.assertEqual(self.profile.title, 'Expert Plumber')
        self.assertEqual(self.profile.city, 'Lahore')

    def test_get_skills_list(self):
        """Skills comma separated string se list mein convert hoti hain"""
        skills = self.profile.get_skills_list()
        self.assertIn('Plumbing', skills)
        self.assertIn('Electrical', skills)

    def test_seller_profile_page_loads(self):
        """Seller profile page logged in contractor ke liye khulti hai"""
        self.browser.login(username='seller@test.com', password='Test@1234')
        response = self.browser.get(reverse('seller_profile'))
        self.assertEqual(response.status_code, 200)


# ─────────────────────────────────────────
# 7. REVIEW TESTS (Unit Tests)
# ─────────────────────────────────────────
class ReviewTest(TestCase):

    def setUp(self):
        self.seller = signin.objects.create_user(
            email='reviewed_seller@test.com',
            name='Reviewed Seller',
            password='Test@1234',
            user_type='contractor'
        )
        self.client_user = signin.objects.create_user(
            email='reviewer@test.com',
            name='Reviewer Client',
            password='Test@1234',
            user_type='client'
        )

    def test_review_created(self):
        """Review successfully banti hai"""
        review = Review.objects.create(
            seller=self.seller,
            client=self.client_user,
            rating=5,
            comment='Bahut acha kaam kiya!'
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.seller, self.seller)

    def test_one_review_per_client_per_seller(self):
        """Ek client ek seller ko sirf ek review de sakta hai"""
        Review.objects.create(
            seller=self.seller,
            client=self.client_user,
            rating=4,
            comment='Acha tha'
        )
        with self.assertRaises(Exception):
            Review.objects.create(
                seller=self.seller,
                client=self.client_user,
                rating=3,
                comment='Duplicate review'
            )