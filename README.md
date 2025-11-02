# ⭐ EthioGurus Platform (Main Repository)

**EthioGurus** is a **proof-of-concept project** developed as Ethiopia's premier managed talent marketplace, aiming to connect top-tier freelance talent with businesses, similar to platforms like Toptal. This system showcases expertise in full-stack development, microservices architecture, and containerization.

This repository serves as the **main entry point** for the containerized application, linking the separate Frontend and Backend services for local deployment using **Docker**.

---

## 🎯 Key Features

* **Client Matching Engine:** Clients are recommended **top freelancers** based on matching their project or job requirements (skills, experience, domain) with the talent profiles in the database.
* **Talent Portal:** Comprehensive profiles, skill verification, and portfolio management components for Gurus.
* **Vetting System:** Multi-stage review process *designed* to ensure only the top 3% of talent is onboarded (supported by external microservices).
* **Containerized Architecture:** Decoupled services for enhanced scalability and maintainability.

---

## 💡 Multi-Container Architecture Approach

The project utilizes a multi-container architecture orchestrated by **Docker Compose** to achieve separation of concerns, scalability, and ease of development.

| Container / Service | Technology | Role | Benefits |
| :--- | :--- | :--- | :--- |
| **Frontend** | React, Tailwind | Presents the UI; communicates with the Backend API. | Independent updates, rapid development (Hot Reloading). |
| **Backend** | Django | Houses the business logic, API endpoints, and matching engine. | Scaled independently of the UI and database load. |
| **Database** | PostgreSQL | Persistent data storage for all services. | Isolated data volume, uses a highly reliable standard image. |
| **Supporting Services** | (e.g., Surveillance/Monitoring , IDVerification , Practical Testing and Theoretical Testing) | Handles specialized tasks external to core business logic. | Promotes a true microservices pattern and code reusability. |

## 🔗 Supporting Vetting and Quality Infrastructure

The EthioGurus platform integrates with several dedicated services and tools to ensure the highest quality talent and maintain system integrity:

| Service | Repository | Main Function | Technologies |
| :--- | :--- | :--- | :--- |
| **ID Verification** | [IDVerification](https://github.com/David-T7/IDVerification) | **Microservice** responsible for processing and validating government-issued talent identification during the onboarding and vetting phase. | (Specific language/framework) |
| **Surveillance/Monitoring** | [Camera-Surveillance-System-](https://github.com/David-T7/Camera-Surveillance-System-) | **Tool** designed to showcase real-time monitoring capabilities, *potentially* for proctoring code tests or securing sensitive areas. | (Specific language/framework) |
| **Practical Testing** | [ethio\_gig\_code\_testing](https://github.com/David-T7/ethio_gig_code_testing) | **Automated testing service** used to evaluate technical competence by running and scoring submissions from prospective Gurus. | (Specific language/framework) |
| **Theoretical Testing** | [ethiogig-testing](https://github.com/David-T7/ethiogig-testing) | **Theoretical Testing for Gurus** (Freelancers) to assess their foundational and specialized knowledge during the vetting process. | (Specific language/framework) |



This approach allows each component to run in its isolated environment, simplifying dependencies, preventing conflicts, and ensuring that a change in the frontend doesn't necessitate restarting the database.

---

## 💻 Tech Stack & Repository Structure

| Component | Technology | Repository |
| :--- | :--- | :--- |
| **Frontend (Web App)** | **React + Tailwind CSS** | [ethiogurus\_frontend](https://github.com/David-T7/ethiogurus_frontend) |
| **Backend (API)** | **Django (Python)** | (Managed here or linked internally) |
| **Containerization** | **Docker / Docker Compose** | Manages service environments and deployment. |
| **Database** | **PostgreSQL** | Primary data storage. |

---

## ⚙️ Setup & Local Run Instructions

To execute this project locally, you must have **Docker** and **Docker Compose** installed.

### Full Installation Guide (Docker)

Execute the following steps in your terminal to clone, configure, build, and start all services:

```bash
# 1. Clone the repository and navigate into the main directory
git clone [https://github.com/David-T7/ethiogig.git](https://github.com/David-T7/ethiogig.git)
cd ethiogig

# 2. Configure Environment Variables
# Create a .env file in the root directory and define essential variables 
# (e.g., POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DJANGO_SECRET_KEY).
# Refer to the individual component READMEs for a full list of required variables.

# 3. Build and Run Containers
# This command will build the images for all services (frontend, backend, db) and start them
docker-compose up --build -d

# 4. Apply Database Migrations
# Run migrations inside the running Django container
# (Assumes your Django service is named 'backend' in docker-compose.yml)
docker-compose exec backend python manage.py migrate

# 5. Create an Admin User
# Create a superuser for accessing the Django admin panel
docker-compose exec backend python manage.py createsuperuser
