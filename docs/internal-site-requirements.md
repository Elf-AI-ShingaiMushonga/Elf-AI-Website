# ELF-AI Internal Consultancy Portal Requirements

## 1. Access and Security
- Internal-only authentication for staff users.
- Role-aware access model (admin, consultant, operations, analyst).
- Secure password storage with hashing.
- Session-based login with explicit logout and inactive-user lockout.

## 2. Delivery Operations
- Dashboard showing active clients, projects, and open tasks.
- Central project board with stage, status, owner, and progress.
- Task visibility with assignees, priorities, and due dates.
- Client registry with account ownership and engagement status.

## 3. Knowledge and Reuse
- Shared resource library for templates, playbooks, and checklists.
- Standard internal operating requirements visible to delivery teams.
- Internal announcements for process and delivery updates.

## 4. Governance and Quality
- Explicit pre-deployment quality controls and requirements.
- Repeatable delivery process to reduce execution variance.
- Clear ownership of accounts and project outcomes.

## 5. Platform and Administration
- CLI capability to create internal users securely.
- Seed hooks to initialize internal reference data.
- Restricted internal route namespace (`/internal/*`) separated from public site.
