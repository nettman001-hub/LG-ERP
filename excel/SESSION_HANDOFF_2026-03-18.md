# Session Handoff - 2026-03-18

## Summary

- Android app is managed separately by the user.
- Desktop app login/OTP flow in `main.py` was changed today.
- LG ERP SMS request failure was traced to the server returning `503 Service Unavailable` from `preLogin.do`.
- A temporary debug-oriented code change in `erp_client.py` was reverted.
- OTP bridge work was updated in PHP.

## PHP OTP Bridge Status

- `otp_upload.php` remains available.
- `otp_delete.php` remains available.
- `otp_latest.php` was changed to read from `otp_log.txt` instead of `otp_store.json`.
- `otp_latest.php` now:
  - accepts `GET`
  - opens `otp_log.txt`
  - finds the latest valid 6-digit OTP from the bottom of the file
  - returns JSON in the existing shape:
    - `ok`
    - `code`
    - `created_at`
  - clears the log file contents after a successful response
  - returns `{"ok": false}` when the file is missing, empty, or contains no valid OTP

## Files Changed Today

- `otp_latest.php`
- `main.py`

## Files Reverted Today

- `erp_client.py`

## Important Notes

- The current environment shell resolves `python` and `py` to WindowsApps stubs, not a usable interpreter.
- A previous handoff note mentions a direct Python path:
  - `C:\Users\PC\AppData\Local\Python\pythoncore-3.14-64\python.exe`
- `php` CLI was not available in this shell, so `php -l otp_latest.php` could not be run here.

## Desktop Login / OTP Flow Status

- `main.py` now auto-clicks the ERP login dialog's `문자 인증번호 받기` button once when the dialog first opens.
- After SMS request success, the old success popup was removed.
- After SMS request success, auto OTP polling does not begin immediately:
  - the app waits about 7 seconds first
  - the waiting label now counts down in real time
  - after the countdown ends, polling for `otp_latest.php` begins
- The OTP wait UI now shows a `대기 취소` button.
- If the user clicks `대기 취소`, the dialog returns to the initial login form state:
  - ID/password fields are enabled again
  - OTP input area is hidden
  - `문자 인증번호 받기` becomes visible again
  - from that point, SMS request must be triggered manually
- If SMS request fails and the user closes the failure popup, the dialog also returns to that same initial login form state.
- The automatic SMS request is only intended for the first dialog open; after cancel/failure reset, the SMS button should be clicked manually.
- The old `ERP 로그인이 완료되었습니다.` popup was removed.
- On OTP verification success, the dialog now closes quietly with no success popup.

## Current Default Credentials In UI

- ERP ID default: `E36401`
- ERP password default: `chak4628))`

## Suggested Restart Point For Tomorrow

1. Deploy the current `otp_latest.php` to `http://unione24.co.kr/otp`.
2. Open the desktop app and confirm the ERP login dialog auto-triggers SMS exactly once on first open.
3. Confirm the 7-second countdown visibly decreases in real time before `otp_latest.php` polling starts.
4. Confirm Android upload writes lines into `otp_log.txt`.
5. Confirm `otp_latest.php` returns the newest OTP once and clears `otp_log.txt` after a successful fetch.
6. Confirm `대기 취소` returns the ERP login dialog to the initial state and requires manual SMS button click afterward.
7. Confirm SMS request failure also returns the dialog to the initial state after the popup is dismissed.
8. Test the full PC auto-OTP flow against the live server when LG ERP is healthy again.
