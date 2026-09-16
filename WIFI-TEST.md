# Riati: first Apple Watch test

The approved action-explanation panel and separate patient/clinician views are implemented. Real accounts and device observations use the new portal; the medication engine remains inside the separate simulated demo.

## Start on this Mac

Double-click **Start Riati.command** inside the project. Keep the terminal open and the Mac awake. It starts the HTTPS pilot on port 8750 and a certificate-only setup page on port 8751. If macOS asks about incoming connections, allow them for this same-Wi-Fi test.

The terminal prints:
- The owner setup address, available on this Mac only.
- The iPhone setup address using this Mac’s current Wi-Fi IP.
- The secure Riati address.
- The test certificate fingerprint to compare before installing it.

Do not use the former `/ingest?hr=...` link. It has been retired. Device uploads now require a patient-specific key and original measurement timestamps.

## Your account

1. Open **http://127.0.0.1:8751/owner** on the Mac.
2. Follow its certificate setup link. In Keychain Access, import the certificate and trust it for SSL only after verifying the fingerprint against the terminal. This is a local test certificate, not a publicly trusted production certificate.
3. Open the secure Riati link and select **Create account**.
4. Enter your own name, email and a password of at least 12 characters.
5. Expand **Have a care-team invitation?** and use the one-use invitation displayed on the owner page.
6. The care-team workspace displays your sharing code. Give that code to your friend.

Email is a login identifier for this local pilot. Email verification, email recovery and professional credential verification are not implemented.

## Your friend’s iPhone

1. Connect the iPhone to the same Wi-Fi as the Mac.
2. In Safari, open the **iPhone certificate setup** address printed on the Mac. It starts with `http://` and ends with `:8751/`.
3. Compare the certificate fingerprint on both screens. Download the Riati certificate profile.
4. Install it in **Settings → General → VPN & Device Management**.
5. Enable trust for the Riati local pilot certificate under **Settings → General → About → Certificate Trust Settings**.
6. Open the secure Riati link from the setup page. Create a normal patient account; leave the care-team invitation blank.
7. Open **Sharing & account**, enter your care-team code, verify your displayed name, and approve sharing.
8. Choose **Connect Apple Watch**, create a private connection, and follow the on-screen Shortcut guide. The upload key is shown once; store it in the Shortcut and do not share it in chat.

The local profile contains only a certificate. No VPN or device-management settings are installed. Remove the profile and its trust after the test. The root certificate expires in 30 days; the server certificate lasts 14 days. If the Mac’s Wi-Fi IP changes, restart Riati and update the Shortcut URL.

## Shortcut: start with heart rate only

1. Open Heart Rate on the Apple Watch and wait for a reading. Check that the reading has reached the paired iPhone’s Health app.
2. In Shortcuts, create a shortcut and add **Find Health Samples**. Type: Heart Rate. Sort by Start Date, latest first. Limit: 1. If other devices also write heart rate, select the Watch source where available, or verify the sample’s source in Health.
3. Get the sample’s **Value** and **Start Date** using **Get Details of Health Samples**. Format the sample date as ISO 8601 with its timezone. Do not replace it with Current Date.
4. Add **Get Contents of URL**, using the upload address shown in Riati, with **POST** and **JSON** request body.
5. Add the `Authorization` header: `Bearer ` followed by the private device key.
6. Add these JSON fields:

| Field | Type | Value |
|---|---|---|
| `metric` | Text | `hr` |
| `value` | Number | The Health sample’s Value variable |
| `measured_at` | Text | Its Start Date formatted as ISO 8601 |
| `source` | Text | `Apple Health via iPhone Shortcut` |

7. Run the Shortcut, granting access to the requested Health type. A successful new sample returns `stored: 1`. Re-sending it returns `duplicates: 1`; its measurement time stays unchanged.
8. Riati refreshes the signed-in record approximately every eight seconds. Both accounts should show the same value and measurement time. Device source is supplied by the uploader, not cryptographically verified.

This is manual syncing for the first test, not continuous background streaming. Health sample arrival depends on the Watch and iPhone. Add oxygen saturation later only if the Watch model, region and Health data support it. Use `spo2`, its numeric value (percent or fraction), and its own measurement date. A missing oxygen sample remains empty.

## What this test does

- Stores actual device-submitted observations under the patient’s account.
- Shows original measurement time and marks old readings.
- Saves patient check-ins and manual care-team replies.
- Lets the care team approve observation-only keyword plans that create an **in-app** review request.
- Explains each recorded action using a snapshot captured at that time.
- Lets the patient revoke sharing, revoke device upload keys, or delete the account and its observations.

No simulated values fill gaps. No treatment is administered or prescribed by the real-reading portal. No emergency service, SMS or email is contacted. The existing clinical demo is separately labelled and simulated.

## Storage and later remote access

Local accounts, health observations, session hashes, device-key hashes and TLS files live in `.riati/`, excluded from Git and never served as web files. Passwords use scrypt when supported, otherwise PBKDF2-SHA256 with 600,000 iterations. Sessions use HttpOnly cookies, CSRF protection and server-enforced access checks. SQLite is not application-encrypted at rest; this is a local pilot on your Mac.

Remote use is not deployed. It needs a stable HTTPS host with a publicly trusted certificate, durable private database storage/backups, verified account invitations or email verification, password recovery, and an operational support process. Do not port-forward the local test server or expose the certificate setup page to the internet.

## Verification performed

Backend tests cover authentication, account isolation, explicit sharing, revocation, immutable explanations, device keys, timestamp validation, duplicate samples, and account deletion. Browser testing covers account creation, shared records, plan matching, incoming test readings, replies, explanation dialogs, mobile layout, Arabic right-to-left layout, and simulated role previews. No real Apple Watch has been paired by these tests.

## Sources

- [Apple: Shortcuts API requests](https://support.apple.com/guide/shortcuts/request-your-first-api-apd58d46713f/ios)
- [Apple: Health data authorization](https://developer.apple.com/documentation/healthkit/authorizing-access-to-health-data)
- [Apple: Trust manually installed certificate profiles](https://support.apple.com/en-us/102390)
- [Apple: Blood Oxygen availability](https://support.apple.com/en-us/120358)
- [OWASP: Password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
