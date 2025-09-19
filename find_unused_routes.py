import re
import glob
from app import app  # make sure app.py defines `app = Flask(__name__)`


def collect_flask_routes(app):
    """Get all registered route endpoints except static."""
    return {
        rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint != "static"
    }


def collect_used_routes():
    """Search templates for url_for, fetch calls, htmx attributes, etc."""
    template_files = glob.glob("templates/**/*.html", recursive=True)
    used = set()

    # regex patterns to catch common usage of routes
    patterns = [
        r"url_for\(\s*'([^']+)'\s*\)",  # url_for('route')
        r'url_for\(\s*"([^"]+)"\s*\)',  # url_for("route")
        r"fetch\(\s*'(/[^']+)'",  # fetch('/api/foo')
        r'fetch\(\s*"(/[^"]+)"',  # fetch("/api/foo")
        r'href="(/[^"]+)"',  # <a href="/something">
        r"hx-(get|post|put|delete)=\"\{\{\s*url_for\(['\"]([^'\"]+)['\"]\)\s*\}\}\"",
    ]

    for f in template_files:
        with open(f, encoding="utf-8") as fh:
            content = fh.read()
            for pat in patterns:
                matches = re.findall(pat, content)
                if not matches:
                    continue

                # Some regexes return tuples (e.g. hx-get with group)
                for m in matches:
                    if isinstance(m, tuple):
                        used.add(m[-1])  # last group is the route name
                    else:
                        if m.startswith("/"):
                            # This is a path, not a route name — normalize later
                            used.add(m)
                        else:
                            used.add(m)
    return used


def normalize_paths_to_endpoints(app, used):
    """Convert hardcoded paths (like '/api/foo/123') into endpoints if they match a Flask rule."""
    endpoints = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue

        # Convert Flask rule syntax to a regex
        # e.g. "/customer/<int:prefill_cust_id>" -> r"^/customer/[^/]+$"
        pattern = "^" + re.sub(r"<[^>]+>", "[^/]+", rule.rule) + "$"

        for u in used:
            if u == rule.endpoint:
                endpoints.add(rule.endpoint)
            elif u.startswith("/") and re.fullmatch(pattern, u):
                endpoints.add(rule.endpoint)

    return endpoints


def main():
    flask_routes = collect_flask_routes(app)
    used_raw = collect_used_routes()
    used_routes = normalize_paths_to_endpoints(app, used_raw)

    unused = flask_routes - used_routes
    print("Unused routes:", unused)


if __name__ == "__main__":
    main()
