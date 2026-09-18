"""Page furniture shared by every fixture.

Deliberately includes IACP's own Facebook/Twitter links and a nav full of
internal links, because that is exactly the noise the extractor has to survive.
"""

HEAD = """<!doctype html><html lang="en"><head>
<meta charset="utf-8"><title>{title} | IACP</title>
<meta property="og:title" content="{title}">
<link rel="stylesheet" href="/assets/site.css">
</head><body>
<header class="site-header">
  <nav class="main-nav">
    <a href="/">Home</a><a href="/about">About</a><a href="/training">Training</a>
    <a href="/news">News</a><a href="/contact">Contact</a>
    <a href="/therapists">Find a Therapist</a>
  </nav>
  <div class="social-links">
    <a href="https://www.facebook.com/IACPdot.ie">Facebook</a>
    <a href="https://twitter.com/IACP_ie">Twitter</a>
    <a href="https://www.linkedin.com/company/iacp">LinkedIn</a>
  </div>
</header>
<main>
"""

FOOT = """
</main>
<footer class="site-footer">
  <a href="https://www.facebook.com/IACPdot.ie">Follow us on Facebook</a>
  <a href="https://www.hse.ie">HSE</a>
  <a href="/privacy">Privacy</a><a href="/cookie-policy">Cookies</a>
  <a href="https://www.somecmsvendor.com">Site by SomeCMS</a>
</footer>
</body></html>
"""


def page(title: str, body: str) -> str:
    return HEAD.format(title=title) + body + FOOT
