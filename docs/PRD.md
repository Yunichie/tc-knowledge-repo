# Product Requirements Document — TC Knowledge Repo (Backend)

**Version:** 1.0
**Date:** 2026-04-22
**Author:** Backend Engineering
**Status:** Draft
**Audience:** ~300 concurrent students, department staff, admins

---

## 1. Product Overview

TC Knowledge Repo is a knowledge-sharing platform for a college department. Students upload, discover, and download academic resources. Admins moderate all submissions before they go public. The system supports three resource types: **PDFs**, **YouTube links**, and **Markdown articles**.

This document defines the **backend scope only**. The frontend (Next.js) is owned by a separate team and communicates exclusively through the REST API defined here.

---

## 2. User Roles & Permissions

| Role | Description | Capabilities |
|------|-------------|--------------|
| **Anonymous** | Unauthenticated visitor | Browse approved resources, search, view details |
| **Student** | Authenticated user | All anonymous capabilities + upload resources, request resources, fulfill requests, report content, trigger bulk downloads |
| **Admin** | Staff/moderator | All student capabilities + approve/reject resources, view reports, manage categories/tags |

> **Auth Boundary:** The backend acts as the Identity Provider. It owns the `users` app, the custom `User` model, and provides endpoints for Registration, Login, and Google OAuth to issue JWTs. The Next.js frontend (e.g. NextAuth) calls these endpoints and attaches the returned JWT as a `Bearer` token to all subsequent API requests.

---

## 3. Core User Flows

### 3.1 Resource Upload Flow

```
Student ──► POST /api/resources/presigned-upload/
            (receives presigned POST URL for R2)
         ──► Upload PDF directly to Cloudflare R2
         ──► POST /api/resources/
            (submit metadata: title, description, type,
             category, tags, r2_object_key / youtube_url / markdown_body)
         ──► Resource created with status=PENDING
         ──► Admin reviews via GET /api/resources/?status=pending
         ──► Admin calls PATCH /api/resources/{id}/moderate/
            (action: approve | reject, rejection_reason)
         ──► If approved: status=APPROVED, visible publicly
         ──► If rejected: status=REJECTED, student notified
```

**Resource Types & Storage:**

| Type | Storage | Upload Method |
|------|---------|---------------|
| PDF | Cloudflare R2 | Presigned POST → direct browser upload |
| YouTube | URL reference only | Student submits URL string |
| Markdown | PostgreSQL (text field) | Student submits raw markdown text |

**Validation Rules:**
- PDF max size: **50 MB** (enforced by presigned URL policy)
- YouTube URL: must match `youtube.com/watch` or `youtu.be/` patterns
- Markdown: max **100,000 characters**
- Title: 3–200 characters
- Description: 10–2000 characters
- Tags: 1–10 per resource
- Category: exactly 1 required

### 3.2 Moderation Flow

```
Admin ──► GET /api/resources/?status=pending
       ──► Reviews resource detail
       ──► PATCH /api/resources/{id}/moderate/
          body: { action: "approve" | "reject", reason?: string }
       ──► Resource status updated
```

**Moderation Rules:**
- Only admins can moderate
- Rejection requires a `reason` string
- Approved resources become publicly searchable
- Rejected resources are visible only to their uploader

### 3.3 Bulk Download Flow

```
Student ──► POST /api/resources/bulk-download/
            body: { category_id?, tag_ids?, search? }
         ──► Backend validates filters, enqueues Celery task
         ──► Returns { task_id: "uuid" }
         ──► Student polls GET /api/resources/bulk-download/{task_id}/
         ──► When complete: { status: "done", download_url: "presigned R2 URL" }
         ──► Presigned URL expires after 1 hour
```

**Implementation Constraints:**
- **MUST** be fully asynchronous (Celery task)
- **MUST NOT** load entire files into memory — stream from R2 in chunks
- Zip is written to a **temporary file on disk**, not in-memory
- Final zip is uploaded back to R2
- Only **APPROVED PDF** resources are included
- Max **100 PDFs** per bulk download request

### 3.4 Resource Request Flow

```
Student A ──► POST /api/requests/
              body: { title, description, category_id? }
           ──► Request created with status=OPEN

Student B ──► PATCH /api/requests/{id}/fulfill/
              body: { resource_id }
           ──► Request status=FULFILLED, linked to resource

Student A ──► DELETE /api/requests/{id}/
           ──► Backend verifies ownership (must be requester) OR Admin status
           ──► Backend deletes request record from PostgreSQL
           ──► Returns 204 No Content
```

### 3.5 Content Reporting Flow

```
Student ──► POST /api/reports/
            body: { resource_id, reason, description }
         ──► Report created with status=OPEN
Admin   ──► GET /api/reports/
         ──► Reviews and resolves
         ──► PATCH /api/reports/{id}/resolve/
            body: { action: "dismiss" | "remove_resource" }
```

**Report Reasons (enum):**
- `COPYRIGHT` — Copyright violation
- `INAPPROPRIATE` — Inappropriate content
- `SPAM` — Spam or misleading
- `DUPLICATE` — Duplicate resource
- `OTHER` — Other (requires description)

### 3.6 Resource Deletion Flow

```
Student/Admin ──► DELETE /api/resources/{id}/
               ──► Backend verifies ownership (must be uploader) OR Admin status
               ──► If Admin, backend verifies an OPEN report exists for this resource AND the resource's status is `REJECTED`
               ──► If PDF, backend deletes file from Cloudflare R2
               ──► Backend deletes resource record from PostgreSQL
               ──► Cascading delete automatically removes associated Reports/Requests
               ──► Returns 204 No Content
```

---

## 4. API Contract

**Base URL:** `/api/`
**Format:** JSON
**Auth Header:** `Authorization: Bearer <token>` (production) / `X-User-Id` + `X-User-Role` (dev stub)

### 4.1 Resources

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/resources/` | Public | List approved resources. Filters: `category`, `tags`, `search`, `type`. Pagination: cursor-based. |
| `POST` | `/resources/` | Student | Submit a new resource (status=PENDING) |
| `GET` | `/resources/{id}/` | Public | Resource detail (approved only; uploaders see their own pending/rejected) |
| `POST` | `/resources/presigned-upload/` | Student | Generate presigned POST URL for R2 PDF upload |
| `PATCH` | `/resources/{id}/moderate/` | Admin | Approve or reject a resource |
| `POST` | `/resources/bulk-download/` | Student | Enqueue bulk PDF download job |
| `GET` | `/resources/bulk-download/{task_id}/` | Student | Poll bulk download task status |
| `DELETE` | `/resources/{id}/` | Student/Admin | Delete a resource and its R2 file. Restricted to the uploader, OR an Admin responding to an open report. |

### 4.2 Categories & Tags

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/categories/` | Public | List all categories |
| `GET` | `/tags/` | Public | List all tags |

### 4.3 Resource Requests

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/requests/` | Public | List open requests |
| `POST` | `/requests/` | Student | Create a resource request |
| `GET` | `/requests/{id}/` | Public | Request detail |
| `PATCH` | `/requests/{id}/fulfill/` | Student | Fulfill a request by linking a resource |
| `DELETE` | `/requests/{id}/` | Student/Admin | Delete a resource request. Restricted to the requester or an Admin. |

### 4.4 Reports

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/reports/` | Student | Report a resource |
| `GET` | `/reports/` | Admin | List all reports |
| `PATCH` | `/reports/{id}/resolve/` | Admin | Resolve a report |

---

## 5. Search & Discovery

**Engine:** PostgreSQL full-text search (`SearchVector` + `SearchQuery`)

**Searchable fields:** `title`, `description`, `markdown_body`

**Filters:**
- `category` — exact match (single category ID)
- `tags` — any match (list of tag IDs, OR logic)
- `type` — exact match (`pdf`, `youtube`, `markdown`)
- `search` — full-text search query string

**Sort options:** `newest` (default), `oldest`, `title_asc`, `title_desc`

**Pagination:** Offset-based with `limit` (default 20, max 100) and `offset`.

---

## 6. System Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Concurrent users | ~300 | Department-scale |
| Max PDF size | 50 MB | R2 presigned policy |
| Max bulk download PDFs | 100 | Prevent memory/disk exhaustion |
| Presigned URL expiry | 1 hour | Security |
| Bulk download zip expiry | 1 hour | Storage hygiene |
| DB connection pooling | Required | Neon serverless has connection limits |
| Task timeout (Celery) | 10 minutes | Prevent stuck workers |

---

## 7. Non-Functional Requirements

- **Latency:** API responses < 500ms (p95) for list/detail endpoints
- **Availability:** Best-effort on free-tier infra; no SLA commitment
- **Security:** Input validation on all endpoints; presigned URLs prevent direct R2 access; SQL injection prevented by ORM
- **Observability:** Structured logging; Celery task status tracking
- **CORS:** Configured for frontend origin only

---

## 8. Tech Stack (Locked)

| Layer | Technology |
|-------|------------|
| Framework | Django 5.x + Django Ninja |
| Database | PostgreSQL 16 (Neon in prod, standard in dev) |
| Task Queue | Celery 5.x |
| Broker/Cache | Redis 7.x |
| Object Storage | Cloudflare R2 (S3-compatible) |
| Package Manager | `uv` |
| Container | Docker + Docker Compose (dev) |
| CI/CD | GitHub Actions |
| Hosting | Azure App Service (API) + Azure VM B1s (workers) |

---

## 9. Out of Scope (v1)

- Email notifications
- Real-time features (WebSockets)
- Resource versioning
- Analytics dashboard
- Rate limiting (defer to reverse proxy)
- File preview/thumbnails
