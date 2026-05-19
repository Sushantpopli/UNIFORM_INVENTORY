# Uniform Inventory Management System

A professional Django-based inventory management system designed to streamline the tracking and management of school uniforms. This application features a premium, modern UI with dark mode, real-time stock tracking, and a fast POS billing interface.

---

## Preview

<div align="center">
  <h3>Modern Dashboard</h3>
  <img src="docs/screenshots/dashboard.png" width="800" alt="Dashboard Overview">
  
  <p align="center">
    <img src="docs/screenshots/billing.png" width="400" alt="POS Billing">
    <img src="docs/screenshots/inventory.png" width="400" alt="Inventory Management">
  </p>
  
  <h3>Real-time Alerts</h3>
  <img src="docs/screenshots/low_stock.png" width="800" alt="Low Stock Alerts">
</div>

---

## Features

-   **School Management**: Maintain a database of schools with unique codes.
-   **Product Catalog**: Manage different types of uniform items (for example, shirts, trousers, and blazers).
-   **Size Tracking**: Define available sizes for each specific product.
-   **Inventory and Pricing**: Track stock levels and set custom prices for each product-size combination per school.
-   **Admin Dashboard**: Full-featured Django admin interface for easy data management.

---

## Tech Stack

-   **Framework**: [Django](https://www.djangoproject.com/)
-   **Database**: SQLite (Default)
-   **Language**: Python 3.x

---

## Prerequisites

Ensure you have Python 3.x installed on your system.

---

## Installation and Setup

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/Sushantpopli/UNIFORM_INVENTORY.git
    cd UNIFORM_INVENTORY
    ```

2.  **Create a Virtual Environment** (Optional but recommended)
    ```bash
    python -m venv venv
    # On Windows:
    venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Run Migrations**
    ```bash
    python manage.py migrate
    ```

5.  **Create a Superuser** (To access the admin panel)
    ```bash
    python manage.py createsuperuser
    ```

6.  **Start the Development Server**
    ```bash
    python manage.py runserver
    ```
    Visit `http://127.0.0.1:8000/admin` to start managing your inventory!

For local HTTP development, set the following in `.env`:

```env
DEBUG=True
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_HSTS_SECONDS=0
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

---

## Project Structure

```text
products/          # Product definitions and models
schools/           # School and inventory (SchoolProduct) logic
sizes/             # Size management per product
uniform_project/   # Core settings and configuration
manage.py          # Django management script
requirements.txt   # Project dependencies
```

---

## Future Roadmap 🚀

We are constantly looking for ways to make UniStock more powerful and easier for shop owners. Our current focus is on safely integrating AI step-by-step:

- [x] **Phase 1: Clean Inventory & Reports** - Establish a robust, error-free database with reliable schema and standard reporting.
- [x] **Phase 2: AI Chat Assistant (Read-only)** - Integrate a local AI to answer natural language questions based on inventory and sales logs (e.g., "Which items are low stock?").
- [ ] **Phase 3: AI Feedback Collection** - Add "Correct" / "Wrong" buttons to the assistant. Store user feedback and corrections as training data for future improvements.
- [ ] **Phase 4: Voice Input** - Allow users to speak their questions directly into the AI assistant.
- [ ] **Phase 5: OCR Bill Scanner (Draft Mode)** - Read supplier bills via camera and create a "draft" restock entry. Requires human review before stock is actually updated.
- [ ] **Phase 6: Custom Fine-Tuning** - Use the feedback data collected in Phase 3 to fine-tune a specialized model tailored to UniStock's specific business context.
- [ ] **Phase 7: Advanced Learning (RL)** - Introduce Reinforcement Learning if the business scale justifies it.
- [ ] **Automated Cloud Backups**: Secure, daily encrypted backups to ensure business data is never lost.
- [ ] **Multi-User Permissions**: Role-based access for staff members with limited permissions.

---

## Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.

---

## License

This project is licensed under the MIT License.

---

**Developed by [Sushant Popli](https://github.com/Sushantpopli)**
