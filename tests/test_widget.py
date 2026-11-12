"""Tests automatisés du composant de pétition (structure HTML et exécution JS)."""

import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
import unittest
from html.parser import HTMLParser


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(ROOT_DIR, "index.html")


class IdCollectorParser(HTMLParser):
    """Collecte tous les attributs id présents dans le document HTML."""

    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for name, value in attrs:
            if name == "id" and value is not None:
                self.ids.append(value)


def read_index():
    """Lit le contenu brut de index.html."""
    with open(INDEX_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def extract_main_script(html_content):
    """Extrait le bloc script principal de index.html."""
    scripts = re.findall(r"<script>(.*?)</script>", html_content, flags=re.DOTALL)
    if not scripts:
        raise ValueError("Aucun bloc script trouvé dans index.html")
    return scripts[-1]


def build_test_harness_html(html_content):
    """Construit une page de test exécutable dans Chrome headless."""
    main_script = extract_main_script(html_content)
    # Remplace l'URL Grist de production par le serveur local de test
    patched_script = main_script.replace(
        'const GRIST_BASE_URL = "https://grist.numerique.gouv.fr";',
        'const GRIST_BASE_URL = window.location.origin;',
    )
    # Empêche le timer de 60s de bloquer la capture DOM
    patched_script = patched_script.replace(
        "setInterval(function() {\n    init();\n  }, 60000);",
        "",
    )
    amp = chr(38)
    harness_js = f"""
<pre id="test-output">PENDING</pre>
<script>
window.addEventListener("error", function(ev) {{
  const out = document.getElementById("test-output");
  if (out) out.textContent = "JS_ERROR:" + ev.message + " (L" + ev.lineno + ")";
}});
</script>
<script>
(async function runTests() {{
  const results = {{ passed: [], failed: [] }};
  function assert(cond, label) {{
    if (cond) {{
      results.passed.push(label);
    }} else {{
      results.failed.push(label);
    }}
  }}

  try {{
    // 1. renderMarkdown échappe le HTML dangereux
    const md = renderMarkdown("Bonjour **tous**\\n\\n- <scr" + "ipt>alert(1)</scr" + "ipt>\\n- point 2");
    assert(md.indexOf("<strong>tous</strong>") !== -1, "renderMarkdown_bold");
    assert(md.indexOf("<scr" + "ipt>") === -1, "renderMarkdown_escapes_script");
    assert(md.indexOf("{amp}lt;script{amp}gt;") !== -1, "renderMarkdown_entities");

    // 2. sanitizeCsvCell et buildRegistryCsv
    assert(sanitizeCsvCell("=1+1") === '"' + "'=1+1" + '"', "csv_formula_eq");
    assert(sanitizeCsvCell("+cmd") === '"' + "'+cmd" + '"', "csv_formula_plus");
    assert(sanitizeCsvCell("-2") === '"' + "'-2" + '"', "csv_formula_minus");
    assert(sanitizeCsvCell("@SUM(A1)") === '"' + "'@SUM(A1)" + '"', "csv_formula_at");
    assert(sanitizeCsvCell('a"b') === '"a""b"', "csv_quotes");
    const csv = buildRegistryCsv([{{ nom: "=Alice", courriel: "a@b.fr", date: 1700000000, commentaire: "ok", rendre_public: true }}]);
    assert(csv.charCodeAt(0) === 0xFEFF, "csv_bom");
    assert(csv.indexOf('"' + "'=Alice" + '";"a@b.fr"') !== -1, "csv_row_sanitized");

    // 3. normalizeColumnTableToRecords
    const normalized = normalizeColumnTableToRecords({{
      id: [10, 11],
      Titre: ["Titre A", "Titre B"],
      Campagne_Ouverte: [1, 0]
    }});
    assert(normalized.length === 2, "normalize_length");
    assert(normalized[0].id === 10, "normalize_id");
    assert(normalized[0].fields.Titre === "Titre A", "normalize_field");

    // 4. displayUnsignedState protège contre XSS sur currentUser
    currentUser = {{ id: 1, name: "<img src=x onerror=alert(1)>", email: "user@example.org", isOwner: false }};
    isCampaignOpen = true;
    displayUnsignedState();
    const badgeEl = document.getElementById("user-connected-badge");
    assert(badgeEl.querySelectorAll("img").length === 0, "xss_no_img_element");
    assert(badgeEl.querySelector("strong").textContent === "<img src=x onerror=alert(1)>", "xss_text_preserved");

    // 5. Chargement REST de bout en bout via init() et mur public
    currentUser = null;
    await init();
    assert(document.getElementById("petition-titre").innerText === "Pétition Test", "rest_title_loaded");
    assert(document.getElementById("count-number").innerText === "2", "rest_count_loaded");
    const wallItems = document.querySelectorAll("#wall-grid-container .supporter-item");
    assert(wallItems.length === 1, "wall_filters_private_signatures");
    assert(wallItems[0].textContent.indexOf("Alice") !== -1, "wall_shows_public_name");

    // 6. Verrou anti-chevauchement sur init()
    await Promise.all([init(), init(), init()]);
    assert(true, "init_concurrent_coalesced");

    // 7. Validation longueur de commentaire et séparation inline vs modal
    let appliedCalls = [];
    isGristEnvironment = true;
    window.grist = {{
      docApi: {{
        applyUserActions: async function(actions) {{
          appliedCalls.push(actions);
        }},
        fetchTable: async function(name) {{
          if (name === "Texte_Petition") {{
            return {{ id: [1], Titre: ["Pétition Test"], Argumentaire: ["Texte"], Nombre_Signatures: [2], Objectif_Signatures: [10], Campagne_Ouverte: [true], Mentions_RGPD: ["RGPD"] }};
          }}
          return {{ id: [], engagement: [], rendre_public: [], date_signature: [], commentaire: [], nom_signataire: [], courriel_signataire: [] }};
        }},
        getAccessToken: async function() {{ return null; }}
      }}
    }};
    document.getElementById("inline-comment").value = "x".repeat(501);
    await submitSignature("inline");
    assert(appliedCalls.length === 0, "inline_rejects_over_500_chars");
    assert(!document.getElementById("inline-sign-error").classList.contains("hidden"), "inline_shows_error");

    document.getElementById("inline-comment").value = "Soutien inline valide";
    document.getElementById("inline-public").checked = true;
    await submitSignature("inline");
    assert(appliedCalls.length === 1, "inline_submits_valid");
    assert(appliedCalls[0][0][3].commentaire === "Soutien inline valide", "inline_reads_own_textarea");

    document.getElementById("input-comment").value = "Soutien modal valide";
    document.getElementById("input-public").checked = false;
    await submitSignature("modal");
    assert(appliedCalls.length === 2, "modal_submits_valid");
    assert(appliedCalls[1][0][3].commentaire === "Soutien modal valide", "modal_reads_own_textarea");

    // 8. Déduplication handleIncomingAction par ts
    const prevToast = document.getElementById("toast-message").innerText;
    handleIncomingAction({{ type: "ACTION_SUCCESS", action: "sign", ts: 9999999999999, user: {{ id: 2, name: "Bob", email: "bob@example.org", isOwner: false }} }});
    document.getElementById("toast-message").innerText = "MARQUEUR";
    handleIncomingAction({{ type: "ACTION_SUCCESS", action: "retract", ts: 9999999999999 }});
    assert(document.getElementById("toast-message").innerText === "MARQUEUR", "incoming_action_deduplicated");
  }} catch (err) {{
    results.failed.push("exception:" + (err ? err.message : String(err)));
  }}

  document.getElementById("test-output").textContent = "TEST_RESULTS:" + JSON.stringify(results);
}})();
</script>
"""
    replaced = html_content.replace(
        '<script src="https://docs.getgrist.com/grist-plugin-api.js"></script>',
        "",
        1,
    )
    replaced = replaced.replace(main_script, patched_script, 1)
    return replaced.replace("</body>", harness_js + "\n</body>", 1)


class MockGristHandler(http.server.BaseHTTPRequestHandler):
    """Serveur HTTP minimal simulant la page de test et les routes REST Grist."""

    harness_html = ""

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/test.html":
            body = self.harness_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if "/tables/Texte_Petition/records" in self.path:
            payload = {
                "records": [
                    {
                        "id": 1,
                        "fields": {
                            "Titre": "Pétition Test",
                            "Argumentaire": "Texte **important**",
                            "Nombre_Signatures": 2,
                            "Objectif_Signatures": 10,
                            "Campagne_Ouverte": True,
                            "Mentions_RGPD": "Mentions RGPD test",
                        },
                    }
                ]
            }
        elif "/tables/Signatures/records" in self.path:
            payload = {
                "records": [
                    {
                        "id": 1,
                        "fields": {
                            "engagement": True,
                            "rendre_public": True,
                            "date_signature": 1700000000,
                            "commentaire": "Pour le collectif",
                            "nom_signataire": "Alice",
                            "courriel_signataire": "",
                        },
                    },
                    {
                        "id": 2,
                        "fields": {
                            "engagement": True,
                            "rendre_public": False,
                            "date_signature": 1700000100,
                            "commentaire": "Confidentiel",
                            "nom_signataire": "Bob",
                            "courriel_signataire": "",
                        },
                    },
                ]
            }
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestPetitionWidget(unittest.TestCase):
    """Vérifie l'intégrité HTML/JS statique et le comportement dans Chrome headless."""

    def test_no_duplicate_dom_ids(self):
        html_content = read_index()
        parser = IdCollectorParser()
        parser.feed(html_content)
        seen = set()
        duplicates = set()
        for dom_id in parser.ids:
            if dom_id in seen:
                duplicates.add(dom_id)
            seen.add(dom_id)
        self.assertEqual(duplicates, set(), f"Identifiants DOM dupliqués : {sorted(duplicates)}")

    def test_no_hardcoded_personal_owner_or_unsafe_badge_innerhtml(self):
        html_content = read_index()
        self.assertNotIn("aguirre.maurin@ofb.gouv.fr", html_content)
        self.assertNotIn("8755", html_content)
        self.assertNotIn("badgeEl.innerHTML", html_content)

    def test_js_behavior_in_headless_chrome(self):
        html_content = read_index()
        MockGristHandler.harness_html = build_test_harness_html(html_content)

        with socketserver.TCPServer(("127.0.0.1", 0), MockGristHandler) as httpd:
            port = httpd.server_address[1]
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            try:
                proc = subprocess.run(
                    [
                        "google-chrome",
                        "--headless",
                        "--disable-gpu",
                        "--virtual-time-budget=3000",
                        "--dump-dom",
                        f"http://127.0.0.1:{port}/test.html",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=True,
                )
            finally:
                httpd.shutdown()

        match = re.search(r'<pre id="test-output">TEST_RESULTS:(\{.*?\})</pre>', proc.stdout)
        self.assertIsNotNone(match, f"Résultats absents du DOM Chrome : {proc.stdout[:1500]}")
        results = json.loads(match.group(1))
        self.assertEqual(results["failed"], [], f"Échecs JS : {results['failed']}")
        self.assertGreaterEqual(len(results["passed"]), 15)


if __name__ == "__main__":
    unittest.main()
