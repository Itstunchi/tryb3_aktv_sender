# Sender

A lightweight, local-first prototype for composing messages, previewing the recipient view, keeping an explicit-consent contact book, and inspecting a delivery activity log.

## Run

Requires Python 3.10 or newer. No packages to install.

```powershell
python app.py
```

Open <http://127.0.0.1:8765>. The prototype binds only to localhost. Add a contact after recording their permission, compose a note, then use **Run demo send**. Demo events are saved in `state.json` on this device. Do not put private data in this prototype; it has no login or encryption.

## Current limits

- Demo mode only: no email or SMS is transmitted.
- The attachment picker is visual only; files are not uploaded or attached.
- The preview is plain text and cannot guarantee how every mail client renders a message.
- Events show a local simulation. A future SMTP integration can report server acceptance/rejection, but confirmed inbox delivery requires provider support and is not universal.
- SMS, provider APIs, HTML/PDF composition, durable audit history, authentication, unsubscribe/suppression, and rate controls are planned before any real sending or sharing.

## Build direction

Keep the first shared release small and opt-in: provider adapters behind a common interface, strict consent/suppression checks, per-provider rate limits, safe secret storage, clear bounce/error messages, and honest status labels. Do not add open recipient imports, sender spoofing, or delivery-evasion features. A PHP adapter can be added later if there is a concrete deployment need; Python is the current prototype runtime.
