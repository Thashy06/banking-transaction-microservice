import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

# ==========================================
# 1. DATABASE LAYER (SQL)
# ==========================================
def init_db():
    """Initializes the SQLite database and creates tables."""
    conn = sqlite3.connect("td_bank.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY,
            owner_name TEXT NOT NULL,
            balance REAL DEFAULT 0.0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            type TEXT,
            amount REAL,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# 2. OOP BUSINESS LOGIC LAYER
# ==========================================
class BankAccount:
    """Encapsulates account balance and handles transactional logic."""
    def __init__(self, account_id, owner_name, balance=0.0):
        self.account_id = account_id
        self.owner_name = owner_name
        self._balance = balance  # Protected attribute (Encapsulation)

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self._balance += amount
        self._sync_db("DEPOSIT", amount)
        return self._balance

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient funds. Overdraft prevented.")
        self._balance -= amount
        self._sync_db("WITHDRAWAL", amount)
        return self._balance

    def get_balance(self):
        return self._balance

    def _sync_db(self, trans_type, amount):
        """Persists state changes to SQLite using SQL queries."""
        conn = sqlite3.connect("td_bank.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE accounts SET balance = ? WHERE account_id = ?",
            (self._balance, self.account_id)
        )
        cursor.execute(
            "INSERT INTO transactions (account_id, type, amount) VALUES (?, ?, ?)",
            (self.account_id, trans_type, amount)
        )
        conn.commit()
        conn.close()

# Helper to fetch account from DB
def load_account(account_id):
    conn = sqlite3.connect("td_bank.db")
    cursor = conn.cursor()
    cursor.execute("SELECT account_id, owner_name, balance FROM accounts WHERE account_id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return BankAccount(account_id=row[0], owner_name=row[1], balance=row[2])
    return None

# ==========================================
# 3. REST API LAYER (FLASK ENDPOINTS)
# ==========================================

@app.route('/account/create', methods=['POST'])
def create_account():
    """POST Endpoint to create a new bank account."""
    data = request.get_json()
    account_id = data.get('account_id')
    owner_name = data.get('owner_name')
    initial_balance = data.get('balance', 0.0)

    conn = sqlite3.connect("td_bank.db")
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO accounts (account_id, owner_name, balance) VALUES (?, ?, ?)",
            (account_id, owner_name, initial_balance)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "Account ID already exists"}), 400
    conn.close()

    return jsonify({"message": "Account created successfully", "account_id": account_id}), 201


@app.route('/account/<int:account_id>/balance', methods=['GET'])
def get_balance(account_id):
    """GET Endpoint to retrieve current account balance."""
    account = load_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404
    
    return jsonify({
        "account_id": account.account_id,
        "owner_name": account.owner_name,
        "balance": account.get_balance()
    }), 200


@app.route('/account/<int:account_id>/deposit', methods=['POST'])
def deposit(account_id):
    """POST Endpoint to deposit money into an account."""
    account = load_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    data = request.get_json()
    amount = data.get('amount', 0.0)

    try:
        new_balance = account.deposit(amount)
        return jsonify({"message": "Deposit successful", "new_balance": new_balance}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/account/<int:account_id>/withdraw', methods=['POST'])
def withdraw(account_id):
    """POST Endpoint to withdraw money with overdraft protection."""
    account = load_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    data = request.get_json()
    amount = data.get('amount', 0.0)

    try:
        new_balance = account.withdraw(amount)
        return jsonify({"message": "Withdrawal successful", "new_balance": new_balance}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ==========================================
# 4. SERVER EXECUTION
# ==========================================
if __name__ == '__main__':
    init_db()
    print("Database initialized. Server starting on http://127.0.0.1:5000 ...")
    app.run(debug=True)
    