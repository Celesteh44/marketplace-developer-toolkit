import json
import re


def build_case_assist(email_text, payload_text):
    payload_summary = _summarize_payload(payload_text)
    seller_signals = _extract_signals(email_text)
    issue = _likely_issue(email_text, payload_summary)
    steps = _steps(issue)
    internal_notes = [
        f"Likely issue: {issue}",
        f"Seller signal(s): {', '.join(seller_signals) if seller_signals else 'No explicit error code found'}",
        f"Payload: {payload_summary}",
        "Recommended action: validate against latest cached spec and confirm product type/version.",
    ]
    response = (
        "Thanks for sharing the details. We are reviewing the submitted payload against the latest Marketplace "
        "specification and checking required fields, allowed values, and data type formatting. Please confirm the "
        "product type and whether this payload was generated from the most recent spec template."
    )
    return {
        "issue": issue,
        "steps": steps,
        "internal_notes": "\n".join(internal_notes),
        "seller_response": response,
    }


def _extract_signals(text):
    signals = []
    for pattern in (r"\bERR[_-]?\d+\b", r"\b\d{3,5}\b", r"missing|required|invalid|enum|schema|taxonomy"):
        signals.extend(re.findall(pattern, text or "", flags=re.I))
    return list(dict.fromkeys(str(signal) for signal in signals))[:8]


def _summarize_payload(payload_text):
    try:
        data = json.loads(payload_text)
        if isinstance(data, dict):
            keys = ", ".join(list(data.keys())[:8])
            return f"JSON object with keys: {keys}"
        return f"JSON {type(data).__name__}"
    except Exception:  # noqa: BLE001 - fallback summary
        trimmed = (payload_text or "").strip()
        if trimmed.startswith("<"):
            return "XML payload"
        return "Payload was not parseable as JSON in the case helper."


def _likely_issue(email_text, payload_summary):
    text = (email_text or "").lower()
    if "enum" in text or "allowed value" in text:
        return "Invalid enum or retired allowed value"
    if "required" in text or "missing" in text:
        return "Missing required field"
    if "type" in text or "array" in text or "schema" in text:
        return "Schema mismatch or incorrect field type"
    if "version" in text or "template" in text:
        return "Outdated specification version"
    if "xml" in payload_summary.lower():
        return "XML structure or namespace issue"
    return "Payload validation issue requiring spec comparison"


def _steps(issue):
    common = [
        "Confirm product type and latest cached spec version.",
        "Run the payload through the validator.",
        "Compare the seller template version against the cached version.",
    ]
    if "enum" in issue.lower():
        return common + ["Check whether the submitted value was removed or renamed in the latest enum list."]
    if "required" in issue.lower():
        return common + ["Identify the missing required path and confirm whether it is conditional."]
    if "outdated" in issue.lower():
        return common + ["Refresh Developer Portal Sync and compare the seller's template version."]
    return common + ["Review data types, array paths, and nested object structure."]
