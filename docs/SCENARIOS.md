# TC Knowledge Repo — User Scenarios & Workflows

This document outlines all possible scenarios and workflows for the functional features of the TC Knowledge Repo application.

## 1. Authentication & Onboarding
All students and admins must have an account to interact with the platform (except for anonymously browsing).

* **Scenario A: A new student joins the platform.**
  * The student navigates to the registration page and provides their email, password, first name, and last name.
  * The app sends this to the backend, which creates a new `User` with the default role `STUDENT`.
  * The student is automatically logged in and receives a JWT token.
* **Scenario B: An existing student logs in.**
  * The student enters their email and password.
  * The backend verifies the credentials and returns a fresh JWT token.
* **Scenario C: Student signs in via Google OAuth (Future Feature).**
  * The student clicks "Sign in with Google", which returns an `id_token`.
  * The app sends this to the backend, which verifies the token, matches or creates the user, and returns a JWT token.

---

## 2. Resource Discovery (Browsing & Searching)
Students and anonymous visitors can discover study materials.

* **Scenario A: Browsing by Category/Tag.**
  * A user clicks on "Linear Algebra" (category) and "Midterms" (tag).
  * The app fetches resources matching these exact filters. Only resources with `status=APPROVED` are returned.
* **Scenario B: Searching by Keyword.**
  * A user types "Calculus derivatives" into the search bar.
  * The backend uses PostgreSQL Full-Text Search to return relevant, approved resources sorted by relevance rank.

---

## 3. Resource Uploads
Students can share materials with their peers. All uploads start as `PENDING`.

* **Scenario A: Uploading a PDF Document.**
  * The student selects a PDF file. The app requests a "ticket" (Presigned PUT URL) from the backend.
  * The app directly uploads the binary file to Cloudflare R2 using the URL.
  * Once R2 accepts the file, the app submits the final Resource metadata (title, category, R2 object key) to the backend.
  * The resource is created but hidden (`PENDING`).
* **Scenario B: Sharing a YouTube Video.**
  * The student pastes a YouTube link. The app submits the URL and metadata directly to the backend.
  * The resource is created as `PENDING`.
* **Scenario C: Writing a Markdown Article.**
  * The student types a long-form article into the rich text editor.
  * The app submits the raw markdown and metadata directly to the backend.
  * The resource is created as `PENDING`.

---

## 4. Moderation (Admin Actions)
To maintain quality, admins review all submissions.

* **Scenario A: Approving a Resource.**
  * An admin views the "Pending Submissions" queue.
  * They review a student's newly uploaded PDF and click "Approve".
  * The backend changes the status to `APPROVED`. The resource is now instantly visible to all students in the main feed.
* **Scenario B: Rejecting a Resource.**
  * An admin reviews a submission and finds it violates guidelines.
  * They click "Reject" and are forced to provide a `reason` (e.g., "Contains copyright answers").
  * The backend changes the status to `REJECTED`. The resource remains hidden, and the uploader can see the rejection reason in their personal dashboard.

---

## 5. Bulk Downloading
Students can download batches of PDFs for offline studying.

* **Scenario A: Requesting a Bulk Zip.**
  * A student filters the feed for "Machine Learning" and clicks "Download All as Zip".
  * The app sends the active filters to the backend, which immediately returns a `task_id`.
  * In the background, a Celery worker streams up to 100 PDFs from Cloudflare R2, packages them into a `.zip` file on the fly, uploads the zip back to R2, and generates a download link.
  * The frontend polls the backend using the `task_id`. Once the status changes to `DONE`, the student receives a secure 1-hour download link.

---

## 6. Resource Requests
Students can ask the community for specific files they are missing.

* **Scenario A: Creating a Request.**
  * Student A cannot find the 2024 Final Exam. They create a Request: "Looking for 2024 Final Exam".
  * The request goes onto the public "Requests Board" with an `OPEN` status.
* **Scenario B: Fulfilling a Request.**
  * Student B sees the request and has the file.
  * Student B clicks "Fulfill" and uploads the PDF.
  * The backend links Student B's new resource to Student A's request, changing the request status to `FULFILLED`.
  * Student A can now click on their fulfilled request to view the resource.
* **Scenario C: Deleting a Request.**
  * Student A finds the 2024 Final Exam on their own, or realizes they made a typo in their request.
  * Student A clicks "Delete Request".
  * The backend verifies Student A is the original requester and deletes the request from the public board. Admins can also delete requests if they are spam or inappropriate.

---

## 7. Content Reporting
Students can flag inappropriate or copyrighted material.

* **Scenario A: Filing a Report.**
  * A student finds a public resource containing sensitive information.
  * They click "Report", select a reason (e.g., `INAPPROPRIATE`), and write a description.
  * A Report is created with status `OPEN` for admins to review.
* **Scenario B: Resolving a Report (Dismissal).**
  * An admin reviews the reported resource, decides it is perfectly fine, and dismisses the report.
  * The report is closed, and the resource remains active.
* **Scenario C: Resolving a Report (Removal).**
  * An admin reviews the reported resource, agrees it violates rules, and resolves the report with action `remove_resource`.
  * The backend changes the offending resource's status from `APPROVED` to `REJECTED` (effectively hiding it from the public) and closes the report.

---

## 8. Resource Deletion
Students can delete resources they previously uploaded. Admins can permanently delete resources, but only as a response to community flags.

* **Scenario A: Student deletes their own resource.**
  * A student views the details of a resource they uploaded.
  * They click "Delete".
  * The backend verifies the student is the original uploader, physically removes the file from Cloudflare R2 (to save storage costs), and deletes the record from the database.
* **Scenario B: Admin purges a reported resource.**
  * An admin reviews the "Reports Queue" and finds a resource that blatantly violates the rules (e.g., highly inappropriate content).
  * The admin clicks "Delete Resource".
  * The backend verifies their Admin role AND verifies that an `OPEN` report exists for this specific resource AND the resource's status is `REJECTED`.
  * The backend deletes the associated R2 file and the database record. The PostgreSQL cascade automatically wipes the report from the queue since the underlying resource no longer exists.
* **Scenario C: Admin attempts to arbitrarily delete a clean resource.**
  * An admin views a resource on the main feed that has *not* been reported by any student.
  * The admin attempts to delete it anyway.
  * The backend verifies the user is an Admin, but blocks the action with a `403 Forbidden` error because there are no pending reports against the resource, preventing unilateral abuse of power.
