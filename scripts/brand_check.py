"""Brand and availability check for OpenGenealogyAI."""
import urllib.request, urllib.parse, json, re, datetime

checks = {}

# 1. Check domain availability for key variants
domains_to_check = [
    "opengenealogyai.com",
    "opengenealogyai.org", 
    "genealogyai.com",
    "genealogyai.org",
    "opengenealogy.ai",
    "genealogy.ai"
]

# Check WHOIS via rdap for each domain
print("=== Domain Availability Check ===")
for domain in domains_to_check:
    try:
        tld = domain.split(".")[-1]
        sld = ".".join(domain.split(".")[:-1])
        
        # RDAP lookup
        rdap_url = f"https://rdap.org/domain/{domain}"
        req = urllib.request.Request(rdap_url, headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            status = data.get("status", [])
            expiry = ""
            for event in data.get("events", []):
                if event.get("eventAction") == "expiration":
                    expiry = event.get("eventDate", "")[:10]
            print(f"  REGISTERED  {domain:<30} expires: {expiry}")
            checks[domain] = {"status": "registered", "expires": expiry}
        except urllib.error.HTTPError as e:
            if e.code == 404:
                print(f"  AVAILABLE   {domain}")
                checks[domain] = {"status": "available"}
            else:
                print(f"  UNKNOWN     {domain} (HTTP {e.code})")
                checks[domain] = {"status": f"http_{e.code}"}
    except Exception as ex:
        print(f"  ERROR       {domain}: {ex}")
        checks[domain] = {"status": "error"}

# 2. GitHub org name check
print("\n=== GitHub Organization Names ===")
github_orgs = ["opengenealogyai", "genealogyai", "opengenealogy"]
for org in github_orgs:
    try:
        req = urllib.request.Request(f"https://api.github.com/orgs/{org}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        print(f"  EXISTS   github.com/{org} - {data.get('name', '')} ({data.get('public_repos', 0)} repos)")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  AVAILABLE  github.com/{org}")
        else:
            print(f"  ERROR  github.com/{org}: HTTP {e.code}")
    except Exception as ex:
        print(f"  ERROR  github.com/{org}: {ex}")

# 3. NPM package name check
print("\n=== NPM Package Names ===")
npm_packages = ["opengenealogyai", "genealogy-ai", "open-genealogy-ai"]
for pkg in npm_packages:
    try:
        req = urllib.request.Request(f"https://registry.npmjs.org/{pkg}", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        print(f"  EXISTS   npm:{pkg} - v{data.get('dist-tags', {}).get('latest', '?')}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  AVAILABLE  npm:{pkg}")
        else:
            print(f"  ERROR  npm:{pkg}: HTTP {e.code}")
    except Exception as ex:
        print(f"  ERROR  npm:{pkg}: {ex}")

# 4. PyPI package name check
print("\n=== PyPI Package Names ===")
pypi_packages = ["opengenealogyai", "genealogy-ai", "open-genealogy-ai"]
for pkg in pypi_packages:
    try:
        req = urllib.request.Request(f"https://pypi.org/pypi/{pkg}/json", headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        print(f"  EXISTS   pypi:{pkg} - v{data['info']['version']}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  AVAILABLE  pypi:{pkg}")
        else:
            print(f"  ERROR  pypi:{pkg}: HTTP {e.code}")
    except Exception as ex:
        print(f"  ERROR  pypi:{pkg}: {ex}")

print("\n=== Summary ===")
print(f"Check completed: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("Our registered: opengenealogyai.org (HG-2 DONE)")
print("Note: Trademark search requires USPTO TESS - manual check recommended")
print("URL: https://tmsearch.uspto.gov/ - search: OpenGenealogyAI, GenealogyAI, OpenGenealogy")
