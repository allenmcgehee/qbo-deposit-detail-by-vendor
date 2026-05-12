# quickbooksdata

Pull QuickBooks Online deposits filtered by the "Received From" vendor on deposit
line items, and write the matching lines to a CSV.

QBO's built-in Deposit Detail report does not let you filter by the vendor on
line items. This script calls the QBO Accounting API directly to get the full
Deposit objects (including line-level `Entity` references), filters them
client-side, and produces a CSV.

## One-time setup

These steps require an Intuit web login, so you have to do them yourself.

1. Sign in / create an account at <https://developer.intuit.com>.
2. **Create an app**: My Hub → Create an app → choose "QuickBooks Online and
   Payments" → give it any name → enable scope
   `com.intuit.quickbooks.accounting`.
3. From the app's **Keys & credentials** page, copy the **Client ID** and
   **Client Secret** for the **Production** environment.
4. Open the **OAuth 2.0 Playground**:
   <https://developer.intuit.com/app/developer/playground>
   - Select the app, scope `com.intuit.quickbooks.accounting`, environment
     Production.
   - Click "Get authorization code" → choose the QuickBooks company → consent.
   - Click "Exchange authorization code for tokens".
   - Copy the **Access Token**, **Refresh Token**, and **Realm ID** (Company
     ID).
5. Copy `.env.example` to `.env` and fill in the four secrets:

   ```
   cp .env.example .env
   ```

   You don't need to keep the access token — the script mints a fresh one on
   every run using the refresh token. Just save the refresh token and realm ID.

Access tokens last 1 hour. Refresh tokens last 100 days and rotate each time
they're used; the script writes the new refresh token back to `.env`
automatically.

## Install

```
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

```
python pull_deposits.py --vendor "Acme Co" --from 2026-01-01 --to 2026-05-12
```

Optional `--out path/to/file.csv` (defaults to `deposits.csv`).

The vendor name must match the **Display Name** in QBO exactly.

### Output columns

| column              | source                                        |
| ------------------- | --------------------------------------------- |
| `deposit_id`        | top-level Deposit Id                          |
| `deposit_date`      | TxnDate                                       |
| `deposit_to_account`| DepositToAccountRef.name                      |
| `line_num`          | Line.LineNum                                  |
| `amount`            | Line.Amount                                   |
| `from_account`      | DepositLineDetail.AccountRef.name             |
| `payment_method`    | DepositLineDetail.PaymentMethodRef.name       |
| `check_num`         | DepositLineDetail.CheckNum                    |
| `memo`              | Line.Description                              |
| `vendor`            | resolved vendor DisplayName                   |

## Sandbox

To test against an Intuit sandbox company instead of production, set
`QBO_ENVIRONMENT=sandbox` in `.env` and re-run the OAuth playground steps with
the sandbox company.

## References

- Deposit object: <https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/deposit>
- Query language: <https://developer.intuit.com/app/developer/qbo/docs/develop/explore-the-quickbooks-online-api/data-queries>
- OAuth refresh: <https://developer.intuit.com/app/developer/qbo/docs/develop/authentication-and-authorization/oauth-2.0#refresh-the-access-token>

## Legal

- [License (MIT)](LICENSE)
- [Privacy policy](PRIVACY.md)
- [Terms of use (EULA)](TERMS.md)
