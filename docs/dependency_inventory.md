# Dependency inventory additions

## `pypdf`

- Declared range: `pypdf>=5.0,<7`.
- Purpose: local, approval-gated text extraction and page-number citation metadata for PDF guidance documents. It is never loaded by static dashboards and does not introduce a browser or network dependency.
- License: BSD 3-Clause, as published by the pypdf project/package metadata.
- Data boundary: parses only documents explicitly allowed by `config/approved_guidance_docs.yaml`; it does not upload files.

The chart-capture implementation uses browser-native DOM/SVG/canvas APIs. No frontend image-capture package, CDN, web framework, or browser-test framework was added.

## PPTX guidance extraction

- Purpose: extract bounded visible text from explicitly approved PowerPoint slide XML with slide-number citations.
- Implementation: Python standard-library `zipfile` and `xml.etree.ElementTree`; no additional runtime dependency or license obligation was introduced.
- Limits: 500 slides, 5 MB uncompressed XML per slide, and 50 MB total slide XML. Speaker notes, embedded files, and image OCR are excluded.

## `pip-system-certs`

- Declared range: `pip-system-certs>=5.3,<6`.
- Purpose: make Python Requests/urllib3 use the operating system certificate store so an organization-managed CA trusted by Windows is also trusted by the dashboard virtual environment.
- License: BSD 3-Clause, as published in the verified PyPI package metadata.
- Runtime behavior: version 5.3 installs a Python startup hook and uses pip's vendored Truststore integration. A new Python process is required after installation.
- Security boundary: certificate verification remains enabled. The dependency does not permit `verify=False`, add a private CA, or replace organizational certificate governance; the relevant issuing CA must already be trusted by the operating system.
