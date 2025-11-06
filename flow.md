Here’s a step-by-step working flow (in diagram-style text) showing how your JWT → Tenant middleware chain works across accounts, tenants, and core:

🧩 Request Flow Overview
🔹 Client → Django Middleware Stack → DRF View

1️⃣ JWTCookieToHeaderMiddleware (accounts/middleware.py)
Incoming HTTP request
     │
     ├── Reads JWT token from HttpOnly cookie (e.g. "access_token")
     │
     ├── If no Authorization header → injects:
     │       request.META["HTTP_AUTHORIZATION"] = "Bearer <token>"
     │
     ▼
Next middleware in chain

2️⃣ JWTAuthenticationMiddleware (accounts/middleware.py)
Receives request with Authorization: Bearer <token>
     │
     ├── Decodes JWT using SECRET_KEY
     │
     ├── Extracts "user_id" → loads User object → sets request.user
     │
     ├── Extracts optional "active_tenant_id" claim
     │       → attaches to request.active_tenant_id
     │
     ▼
Next middleware in chain

3️⃣ TenantMiddleware (tenants/middleware.py)
Receives request with request.user + (maybe) request.active_tenant_id
     │
     ├── Skips public paths (/api/auth/, /admin/, etc.)
     │
     ├── Checks if user.is_authenticated
     │       ❌ → raise NotAuthenticated
     │
     ├── If user.is_super_admin() → skip tenant binding
     │
     ├── Else, resolve tenant:
     │       • Try request.active_tenant_id (from JWT)
     │       • Fallback: query TenantMembership for user's active tenant
     │
     ├── Sets request.tenant = Tenant object
     │
     ▼
Next middleware or DRF View

4️⃣ TenantViewSet / TenantQuerysetMixin (core/mixins.py)
When DRF ViewSet executes:
     │
     ├── get_queryset() → filters data by request.tenant
     │       e.g.  queryset.filter(tenant=request.tenant)
     │
     ├── perform_create() → auto-sets tenant on new objects
     │       serializer.save(tenant=request.tenant)
     │
     ▼
Response returned with tenant-isolated data ✅

🧠 Summary Flow
[ Client ]
   ↓
[ JWTCookieToHeaderMiddleware ]
   ↓
[ JWTAuthenticationMiddleware ] → attaches user + active_tenant_id
   ↓
[ TenantMiddleware ] → attaches request.tenant (resolves tenant)
   ↓
[ DRF View / TenantViewSet ] → filters and saves data per tenant
   ↓
[ Response ]


✅ Result:

Each request is fully authenticated and tenant-scoped.

No cross-tenant data leakage.

SuperAdmin can bypass tenant filtering when needed.