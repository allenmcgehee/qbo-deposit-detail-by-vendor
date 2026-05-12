# Privacy Policy

This software (the "Tool") is a self-hosted command-line script that connects
to a single QuickBooks Online company on behalf of the person running it.

## What the Tool collects

Nothing. The Tool runs locally on the operator's own computer. It does not
operate any servers, websites, or third-party services.

## What the Tool stores

The Tool reads OAuth credentials (Client ID, Client Secret, Refresh Token, and
Realm ID) from a local `.env` file on the operator's computer. These
credentials never leave the local machine except when sent directly to
Intuit's OAuth and QuickBooks Online API endpoints to authenticate and fetch
data.

The Tool writes deposit data fetched from QuickBooks Online to a CSV file on
the operator's local disk. This data is not transmitted to any third party.

## What the Tool transmits

The Tool communicates only with the following Intuit-operated endpoints:

- `https://oauth.platform.intuit.com` — token refresh
- `https://quickbooks.api.intuit.com` — QuickBooks Online API (production)
- `https://sandbox-quickbooks.api.intuit.com` — QuickBooks Online API (sandbox)

No telemetry, analytics, error reporting, or any other outbound traffic is
sent by the Tool.

## Cookies and tracking

The Tool is a command-line script with no web interface and does not use
cookies, tracking pixels, fingerprinting, or any similar mechanism.

## Data sharing

The Tool does not share any data with anyone. The only party that receives any
data is Intuit, and only the data necessary to authenticate the operator and
fulfill the operator's own QuickBooks Online API requests.

## Contact

Questions about this policy can be raised by opening an issue on the project's
public repository.
