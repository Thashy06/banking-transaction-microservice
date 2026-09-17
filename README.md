# Banking Transaction & Audit Microservice

A production-ready RESTful banking microservice built with **Python**, **Flask**, and **SQLite**. The system handles standard core banking operations—such as account creation, deposits, withdrawals, and balance inquiries—while embedding Object-Oriented Programming (OOP) business logic, overdraft validation, and an automated compliance audit engine to log transactions exceeding regulatory thresholds ($10,000+).

---

## Technical Stack & Architecture

* **Backend Framework:** Python / Flask (REST API)
* **Database:** SQLite3 (State persistence & Compliance logging)
* **Architecture:** Object-Oriented Programming (OOP) domain model integrated with dynamic SQL persistence layer
* **Testing Tooling:** REST Client / `curl`

---

## Key Features

* **OOP Domain Model (`BankAccount`):** Encapsulates core business rules, internal balance modification, dynamic validation, and database state synchronization.
* **Overdraft & Input Protection:** Prevents negative balances and invalid amounts by raising explicit exceptions mapped to `400 Bad Request` HTTP responses.
* **Automated Compliance Audit Engine:** Automatically intercepts high-value transactions ($\ge \$10,000.00$)—such as Anti-Money Laundering (AML) checks—and logs audit flags with timestamps into a dedicated `audit_flags` table.
* **RESTful Endpoints:** Exposes operational banking methods and compliance logs via JSON APIs.

---

## Database Schema

* `accounts`: Stores `account_id`, `owner_name`, and persistent `balance`.
* `transactions`: Logs transaction ledgers (`trans_id`, `account_id`, `type`, `amount`).
* `audit_flags`: Captures high-risk transfers ($\ge \$10,000$) (`flag_id`, `account_id`, `trans_type`, `amount`, `flag_reason`, `timestamp`).

---

## API Reference

### 1. Create Account
* **Endpoint:** `POST /account/create`
```
* **Request Body:**
  ```json
  {
    "account_id": 101,
    "owner_name": "Jane Doe",
    "balance": 500.0
  }

  {
  "account_id": 101,
  "message": "Account created successfully"
}
