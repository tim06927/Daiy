# Security Documentation: Consent Page Redirects

## Overview

This document describes the security measures implemented to prevent open redirect vulnerabilities in the consent page redirect mechanism.

## Problem Statement

The original issue (PR #55) added functionality to preserve the `next` parameter across POST requests to allow users to continue to their intended destination after providing consent. However, this introduced potential open redirect vulnerabilities that needed to be addressed.

## Security Implementation

### URL Validation Functions

Two security functions in `web/app.py` handle URL validation:

#### `_is_safe_redirect_url(target: str) -> bool`

Validates that a redirect URL is safe for internal use only. Returns `True` only if the URL passes all security checks.

**Security Checks:**
1. **Empty URL Check**: Rejects empty or None URLs
2. **Scheme Check**: Rejects URLs with any scheme (http://, https://, javascript:, data:, file:, etc.)
3. **Netloc Check**: Rejects URLs with hostnames (domain.com, evil.com, etc.)
4. **Protocol-Relative Check**: Rejects protocol-relative URLs (//example.com)
5. **Backslash Variants Check**: Rejects URLs starting with /\ or \/ (could be misinterpreted)
6. **Leading Slash Check**: Requires URLs to start with / to be valid internal paths

#### `_get_safe_redirect_url(url: Optional[str], default: str = "/") -> str`

Wraps `_is_safe_redirect_url()` to provide a safe fallback. If the requested URL is unsafe, it returns the default URL (typically "/").

### Usage in Consent Route

The consent route (`/consent`) uses these functions in both GET and POST requests:

```python
@app.route("/consent", methods=["GET", "POST"])
def consent() -> Union[str, Response]:
    # Validate redirect URL from form data or query args
    next_param = request.form.get("next") or request.args.get("next")
    next_url = _get_safe_redirect_url(next_param, "/")
    
    if request.method == "POST":
        if request.form.get("consent"):
            session["alpha_consent"] = True
            session["alpha_consent_ts"] = datetime.now(timezone.utc).isoformat()
            return redirect(next_url)  # Safe redirect
    
    return render_template("consent.html", next_url=next_url)
```

## Test Coverage

### Unit Tests (15 tests)

Testing `_is_safe_redirect_url()` directly:
- ✅ Rejects external HTTPS URLs
- ✅ Rejects external HTTP URLs
- ✅ Rejects javascript: URLs
- ✅ Rejects data: URLs
- ✅ Rejects protocol-relative URLs (//)
- ✅ Rejects backslash variants (/\, \/)
- ✅ Rejects URLs without leading slash
- ✅ Rejects empty/None values
- ✅ Accepts root path (/)
- ✅ Accepts internal paths
- ✅ Accepts paths with query strings
- ✅ Accepts paths with fragments

Testing `_get_safe_redirect_url()`:
- ✅ Returns valid URLs unchanged
- ✅ Returns default for invalid URLs
- ✅ Supports custom default values

### Integration Tests (17 tests)

Testing end-to-end redirect behavior:
- ✅ Rejects external URLs in POST data
- ✅ Rejects protocol-relative URLs
- ✅ Rejects javascript: URLs
- ✅ Rejects data: URLs
- ✅ Rejects file: URLs
- ✅ Rejects backslash-slash URLs
- ✅ Rejects slash-backslash URLs
- ✅ Rejects URLs without leading slash
- ✅ Rejects empty next parameter
- ✅ Rejects URL-encoded external URLs
- ✅ Allows valid internal paths
- ✅ Allows paths with query strings
- ✅ Allows paths with fragments
- ✅ Allows paths with query and fragment
- ✅ Sanitizes next URL in GET requests
- ✅ Preserves next from query string
- ✅ Preserves next from form data

## Attack Vectors Addressed

### 1. External URL Redirect
**Attack**: `?next=https://evil.com`  
**Protection**: Rejected by scheme check

### 2. Protocol-Relative URL
**Attack**: `?next=//evil.com`  
**Protection**: Rejected by explicit protocol-relative check

### 3. JavaScript Execution
**Attack**: `?next=javascript:alert(1)`  
**Protection**: Rejected by scheme check

### 4. Data URI
**Attack**: `?next=data:text/html,<script>alert(1)</script>`  
**Protection**: Rejected by scheme check

### 5. File Access
**Attack**: `?next=file:///etc/passwd`  
**Protection**: Rejected by scheme check

### 6. Backslash Confusion
**Attack**: `?next=/\evil.com` or `?next=\/evil.com`  
**Protection**: Rejected by backslash variant check

### 7. URL Encoding
**Attack**: `?next=%2F%2Fevil.com` (encoded //)  
**Protection**: Rejected because decoded URL doesn't start with /

### 8. Missing Leading Slash
**Attack**: `?next=evil.com`  
**Protection**: Rejected by leading slash requirement

## Manual Verification

The implementation was manually tested with the following scenarios:

1. **Basic Navigation**: Clicking Continue on consent page → redirects to home (/)
   - ✅ Verified with screenshot

2. **Query String Preservation**: `/consent?next=/search?q=test` → redirects to `/search?q=test`
   - ✅ Verified URL preserved correctly

3. **Form Data Preservation**: POST with `next=/api/categories` → redirects to `/api/categories`
   - ✅ Verified redirect works

## Security Review Results

- **Code Review**: No issues found
- **CodeQL Analysis**: 0 alerts found
- **Test Results**: 61/62 tests passing (1 unrelated DB configuration issue)

## Recommendations

1. **Keep Functions Private**: The underscore prefix (`_is_safe_redirect_url`) indicates these are internal functions. Keep them that way.

2. **Don't Bypass Validation**: Always use `_get_safe_redirect_url()` when handling redirect URLs. Never use the raw `next` parameter directly.

3. **Test New Features**: When adding new redirect functionality, ensure it uses the existing validation functions.

4. **Review Dependencies**: If updating Flask or urllib.parse, re-run security tests to ensure behavior hasn't changed.

## References

- [OWASP: Unvalidated Redirects and Forwards](https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/11-Client-side_Testing/04-Testing_for_Client-side_URL_Redirect)
- [CWE-601: URL Redirection to Untrusted Site ('Open Redirect')](https://cwe.mitre.org/data/definitions/601.html)
