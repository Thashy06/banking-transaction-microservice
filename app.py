import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

# ==========================================
# 1. DATABASE LAYER (SQL + AUDIT LOG)
# ==========================================
def init_db():
    """Initializes SQLite database, including the audit flags table."""
    conn = sqlite3.connect("td_bank.db")
    cursor = conn.cursor()
    
    # Accounts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            account_id INTEGER PRIMARY KEY,
            owner_name TEXT NOT NULL,
            balance REAL DEFAULT 0.0
        )
    ''')
    
    # Standard transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            type TEXT,
            amount REAL,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        )
    ''')
    
    # NEW: Automated Audit / Compliance Flags table ($10,000+ threshold)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_flags (
            flag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            trans_type TEXT,
            amount REAL,
            flag_reason TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (account_id) REFERENCES accounts(account_id)
        )
    ''')
    conn.commit()
    conn.close()

# ==========================================
# 2. OOP BUSINESS LOGIC & AUDIT ENGINE
# ==========================================
class BankAccount:
    """Encapsulates account balance, transactional logic, and audit rules."""
    LARGE_TRANSACTION_THRESHOLD = 10000.0  # Regulatory FINTRAC / AML threshold

    def __init__(self, account_id, owner_name, balance=0.0):
        self.account_id = account_id
        self.owner_name = owner_name
        self._balance = balance

    def deposit(self, amount):
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self._balance += amount
        self._sync_db("DEPOSIT", amount)
        self._run_audit_engine("DEPOSIT", amount)  # Run automated audit check
        return self._balance

    def withdraw(self, amount):
        if amount <= 0:
            raise ValueError("Withdrawal amount must be positive.")
        if amount > self._balance:
            raise ValueError("Insufficient funds. Overdraft prevented.")
        self._balance -= amount
        self._sync_db("WITHDRAWAL", amount)
        self._run_audit_engine("WITHDRAWAL", amount)  # Run automated audit check
        return self._balance

    def get_balance(self):
        return self._balance

    def _sync_db(self, trans_type, amount):
        """Persists standard state changes to SQLite."""
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

    def _run_audit_engine(self, trans_type, amount):
        """AUTOMATED AUDIT ENGINE: Flags high-risk transfers >= $10,000."""
        if amount >= self.LARGE_TRANSACTION_THRESHOLD:
            conn = sqlite3.connect("td_bank.db")
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO audit_flags (account_id, trans_type, amount, flag_reason) 
                   VALUES (?, ?, ?, ?)''',
                (
                    self.account_id, 
                    trans_type, 
                    amount, 
                    f"HIGH_RISK_THRESHOLD_EXCEEDED: Transfer of ${amount:,.2f} >= $10,000.00"
                )
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
# 3. REST API LAYER (ENDPOINTS)
# ==========================================

@app.route('/account/create', methods=['POST'])
def create_account():
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

    # If initial deposit is $10,000+, run audit check
    if initial_balance >= BankAccount.LARGE_TRANSACTION_THRESHOLD:
        acct = BankAccount(account_id, owner_name, initial_balance)
        acct._run_audit_engine("INITIAL_DEPOSIT", initial_balance)

    return jsonify({"message": "Account created successfully", "account_id": account_id}), 201


@app.route('/account/<int:account_id>/balance', methods=['GET'])
def get_balance(account_id):
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
    account = load_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    data = request.get_json()
    amount = data.get('amount', 0.0)

    try:
        new_balance = account.deposit(amount)
        flagged = amount >= BankAccount.LARGE_TRANSACTION_THRESHOLD
        return jsonify({
            "message": "Deposit successful",
            "new_balance": new_balance,
            "compliance_flagged": flagged
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


@app.route('/account/<int:account_id>/withdraw', methods=['POST'])
def withdraw(account_id):
    account = load_account(account_id)
    if not account:
        return jsonify({"error": "Account not found"}), 404

    data = request.get_json()
    amount = data.get('amount', 0.0)

    try:
        new_balance = account.withdraw(amount)
        flagged = amount >= BankAccount.LARGE_TRANSACTION_THRESHOLD
        return jsonify({
            "message": "Withdrawal successful",
            "new_balance": new_balance,
            "compliance_flagged": flagged
        }), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# NEW ENDPOINT: Audit dashboard endpoint to view flagged high-risk transactions
@app.route('/audit/flags', methods=['GET'])
def get_audit_flags():
    """GET Endpoint: Retrieves all flagged transfers exceeding regulatory thresholds."""
    conn = sqlite3.connect("td_bank.db")
    cursor = conn.cursor()
    cursor.execute("SELECT flag_id, account_id, trans_type, amount, flag_reason, timestamp FROM audit_flags")
    rows = cursor.fetchall()
    conn.close()

    flags = []
    for r in rows:
        flags.append({
            "flag_id": r[0],
            "account_id": r[1],
            "trans_type": r[2],
            "amount": r[3],
            "flag_reason": r[4],
            "timestamp": r[5]
        })
    return jsonify({"audit_flags": flags, "total_flagged": len(flags)}), 200


# ==========================================
# 4. SERVER EXECUTION
# ==========================================
if __name__ == '__main__':
    init_db()
    print("Database & Audit Engine initialized. Server running on http://127.0.0.1:5000 ...")
    app.run(debug=True)