<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0a1628,50:1a3a6b,100:c9903a&height=180&section=header&text=ContractorHub&fontSize=65&fontColor=ffffff&fontAlignY=38&desc=Pakistan%20ka%20%231%20Construction%20Platform&descAlignY=58&descColor=e8a84a&animation=fadeIn" width="100%"/>

<br/>

[![Django](https://img.shields.io/badge/Django-5.x-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Groq AI](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036?style=for-the-badge&logo=meta&logoColor=white)](https://groq.com)
[![Google OAuth](https://img.shields.io/badge/Google-OAuth2-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://developers.google.com)

<br/>

**ContractorHub** connects clients with skilled contractors (plumbers, electricians, painters & more) across Pakistan — with role-based dashboards, real-time messaging, AI-powered matching, and proposal analytics.

</div>

---

## 🗺️ User Flow

```mermaid
flowchart LR
    A([🌐 Home]) --> B([⏳ Loader])
    B --> C([🎯 Landing Page\nPick Role])
    C -->|Client| D([📋 Signup / Login])
    C -->|Contractor| D
    D -->|Google OAuth| E{Role?}
    D -->|Email| E
    E -->|Client| F([🏠 Client Dashboard])
    E -->|Contractor| G([🔨 Seller Dashboard])
    F --> H([🔍 Browse Contractors])
    F --> I([💬 Messages])
    G --> J([📝 Manage Proposals])
    G --> K([👤 Profile Editor])
    H --> I
    J --> L([📊 Impression Analytics])
```

---

## 🗄️ Database Schema

```mermaid
erDiagram
    signin ||--o| Seller_Profile : "has"
    signin ||--o| Client_Profile : "has"
    Seller_Profile ||--o{ WorkExperience : "has many"
    Seller_Profile ||--o{ Certificate : "has many"
    Seller_Profile ||--o{ Proposal : "creates"
    Proposal ||--o{ ProposalImpression : "tracks"
    signin }o--o{ Conversation : "participants"
    Conversation ||--o{ Message : "contains"
    Message }o--o| Proposal : "attaches"
    signin ||--o{ Review : "receives (seller)"
    signin ||--o{ Review : "gives (client)"

    signin {
        string email PK
        string name
        string user_type
        string phone
        url profile_image
    }
    Seller_Profile {
        string title
        string skills
        string city
        string language
        text about
        decimal avg_rating
        int level
        bool is_available
        image profile_photo
        image cover_photo
    }
    Client_Profile {
        string city
        string language
        string company_name
        image profile_photo
    }
    Proposal {
        string title
        string work_type
        string search_tag
        decimal base_price
        string delivery_time
        image portfolio_image
        file doc_portfolio
        file video_intro
        bool is_active
    }
    Review {
        int rating
        text comment
    }
    WorkExperience {
        string job_title
        string company
        date start_date
        date end_date
        bool is_current
    }
    Certificate {
        string title
        file file
    }
    Message {
        text content
        bool is_read
    }
```

---

## 🤖 AI Assistant Architecture

```mermaid
sequenceDiagram
    participant U as User (Browser)
    participant D as Django View
    participant G as Groq API

    U->>D: GET /ai-context/
    D->>D: Detect role (client/contractor)
    D->>D: Build context from DB
    D-->>U: {role, welcome, context}

    U->>D: POST /ai-chat/ {message, history[]}
    D->>D: Prepend system prompt + DB context
    D->>G: llama-3.3-70b-versatile
    G-->>D: AI reply
    D-->>U: {reply}
```

> **Client AI** → recommends best contractors from live DB data  
> **Seller AI** → coaches on profile quality, proposals, pricing strategy

---

## 📁 Pages & Routes

| Template | URL | Access | Status |
|---|---|---|---|
| `landingpage.html` | `/landing_page/` | Public | ✅ |
| `login.html` | `/login/` `/signin/` | Public | ✅ |
| `client.html` | `/client/` | Login Required | ✅ |
| `show_seller.html` | `/show_seller/` | Login Required | ✅ |
| `seller.html` | `/seller/` | Login Required | ✅ |
| `profile_seller.html` | `/seller/profile/` | Login Required | ✅ |
| `proposal.html` | `/seller/proposal/create/` | Login Required | ✅ |
| `active_work.html` | `/proposals/` | Login Required | ✅ |
| `messages.html` | `/messages/` | Login Required | ✅ |
| `profile_view.html` | `/profile/<id>/` | Login Required | ✅ |
| `client_profile.html` | `/client/profile/` | Login Required | ✅ |
| `admin.html` | `/myadmin/` | Admin | ⚠️ UI only |
| `home.html` `faqs.html` `about_us.html` `privacy.html` | various | Public | ✅ |

---

## ⚙️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5, Python 3.11 |
| Auth | Django Auth + Google OAuth (allauth) |
| AI | Groq API — LLaMA 3.3 70B Versatile |
| Frontend | HTML, CSS (custom vars), Vanilla JS |
| Charts | Chart.js (impression analytics) |
| Storage | Django FileField / ImageField → `/media/` |
| Maps | Nominatim reverse geocoding (client-side) |
| DB | SQLite (dev) → PostgreSQL (prod) |

---

## 🚀 Setup

```bash
# 1. Install dependencies
pip install django django-allauth groq python-dotenv Pillow

# 2. Create env.env in project root
SECRET_KEY=your-secret-key
GROQ_API=gsk_your_groq_key
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# 3. Run migrations
python manage.py makemigrations && python manage.py migrate

# 4. Start server
python manage.py runserver
# Visit → http://localhost:8000/loader/
```

---

## 🔐 Security Status

| Feature | Status |
|---|---|
| CSRF Protection on all forms | ✅ |
| `@login_required` on all sensitive views | ✅ |
| Role-based redirect enforcement | ✅ |
| Conversation access control | ✅ |
| Strong password validation | ✅ |
| Review self-submission blocked | ✅ |
| Rate limiting on login/AI endpoints | ❌ Needed |
| `/myadmin/` auth guard | ❌ Needed |
| File upload type/size validation | ❌ Needed |
| Email verification on signup | ❌ Needed |
| HTTPS enforcement (production) | ❌ Needed |

---

## 🛣️ Roadmap

- [ ] Admin panel backend (user management, moderation, stats)
- [ ] Notification system (new message, new review, new view)
- [ ] Payment integration (JazzCash / EasyPaisa)
- [ ] WebSocket real-time messaging (replace 5s polling)
- [ ] Email verification + password reset
- [ ] Rate limiting on auth + AI endpoints
- [ ] Distance-based contractor discovery

---

## 📸 Screenshots

| Landing Page | Client Dashboard | Seller Dashboard |
|:---:|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/f58d0b6f-ec5a-44e0-b9b9-1b0d91bbfca4" width="100%"/> | <img src="https://github.com/user-attachments/assets/aa8b8666-2677-4d49-9e68-77e49ef26417" width="100%"/> | <img src="https://github.com/user-attachments/assets/492ede3e-d7a2-412a-accf-1a6ec1a11fa5" width="100%"/> |

| Messages | Profile Editor |
|:---:|:---:|
| <img src="https://github.com/user-attachments/assets/1a956680-77f0-4745-ae40-28966cffcdbe" width="100%"/> | <img src="https://github.com/user-attachments/assets/d792c20f-1a5f-4b4a-93f5-281ecf25d971" width="100%"/> |

---

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:c9903a,100:0a1628&height=100&section=footer" width="100%"/>

Made with ❤️ for Pakistan's Construction Industry

</div>
