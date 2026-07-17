# Read-only finding dispositions

Dashboard 5 may merge a separately maintained JSON disposition register from the path configured by `paths.finding_dispositions` in `config/settings.yaml`. The default is `data/curated/finding_dispositions.json`, which remains ignored by Git.

The file must be a JSON array. Each object is validated strictly and supports:

- `finding_id`: required existing generated finding ID; duplicate and unknown IDs fail the build.
- `owner`: optional responsible organization or role.
- `status`: one of `new`, `under_review`, `response_received`, `resolved`, or `accepted_risk`.
- `due_date`: optional ISO `YYYY-MM-DD` date.
- `management_response`: optional controlled response text.
- `analyst_disposition`: optional analyst review text.

Example with synthetic placeholders:

```json
[
  {
    "finding_id": "replace_with_generated_finding_id",
    "owner": "Example review role",
    "status": "under_review",
    "due_date": "2028-09-30",
    "management_response": null,
    "analyst_disposition": "Pending evidence review."
  }
]
```

The browser is read-only. It cannot update dispositions, source data, or findings. Protect the controlled register under the same governance rules as other curated analytical inputs; do not place controlled responses in public/static hosting unless approved.
