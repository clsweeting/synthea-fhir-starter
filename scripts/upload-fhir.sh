#!/usr/bin/env bash
set -euo pipefail

FHIR="${FHIR:-http://localhost:8080/fhir}"

post_file () {
  local f="$1"
  # try gzip if available (smaller/faster)
  if command -v gzip >/dev/null; then
    gzip -c "$f" | curl -sS -o /tmp/resp.json -w "%{http_code}\n" \
      -H "Content-Type: application/fhir+json" \
      -H "Content-Encoding: gzip" \
      --data-binary @- "$FHIR"
  else
    curl -sS -o /tmp/resp.json -w "%{http_code}\n" \
      -H "Content-Type: application/fhir+json" \
      --data-binary @"$f" "$FHIR"
  fi
}

echo "== Preloading infrastructure bundles =="
shopt -s nullglob
for f in output/fhir/practitionerInformation*.json output/fhir/hospitalInformation*.json; do
  echo "POST $f"
  code=$(post_file "$f") || code="000"
  if [[ "$code" != "200" && "$code" != "201" ]]; then
    echo "  ⚠️  Infra load failed ($code) for $f"
    cat /tmp/resp.json; echo
  fi
done

echo "== Uploading per-patient bundles =="
ok=0; fail=0
for f in output/fhir/*.json; do
  [[ "$f" == *practitionerInformation* || "$f" == *hospitalInformation* ]] && continue
  echo "POST $f"
  code=$(post_file "$f") || code="000"
  if [[ "$code" == "200" || "$code" == "201" ]]; then
    ok=$((ok+1))
  else
    fail=$((fail+1))
    echo "  ⚠️  failed ($code): $(jq -r '.issue[0].diagnostics? // empty' /tmp/resp.json)"
  fi
  # small pause helps with large servers/indexing
  sleep 0.1
done

echo "Done. Success: $ok  Failed: $fail"
echo "Patients now in server:"
curl -s "$FHIR/Patient?_summary=count" | jq -r '.total'