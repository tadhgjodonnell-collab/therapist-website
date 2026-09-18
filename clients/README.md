# Client content files

One JSON per paying client. Copy `example.json`, replace the bracketed
placeholders with what the client actually tells you, then:

```bash
python -m iacp_leads site --content clients/their-name.json \
       --out build/their-name --live
```

`--live` drops the draft banner and makes the page indexable. Leave it off
while you're still sending versions back and forth.

Every key in the file maps to a placeholder in `site/template.html`, so you
can add or rename fields there and they'll be available here.
