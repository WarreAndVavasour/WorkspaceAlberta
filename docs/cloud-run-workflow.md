# Cloud Run release workflow

Use **Actions → Deploy to Cloud Run → Run workflow**, with branch **main**.
The workflow is manual: merging or pushing alone does not change production.

## Release in two runs

1. Select **stage**. Leave the revision inputs blank. The workflow runs the local
   test suites, builds only the tracked application files, pushes the image to
   Artifact Registry, and deploys its immutable digest at zero production traffic.
   It checks OAuth discovery, all 26 tool titles, authentication challenges,
   Google sign-in rendering, exact image hashes, search, details and matching.
2. Open the successful run's summary. Copy **revision** and **previous_revision**.
3. Run the same workflow on **main** with **promote**. Enter those values as
   **revision** and **expected_current**, respectively. This is the explicit
   production release decision. It verifies the candidate again, moves 100% of
   traffic to that exact revision, then repeats the checks on the public domain.

Both actions share a concurrency lock and never cancel an active release.
Promotion refuses split traffic, a stale previous revision, a revision from
another service, an image outside our registry, a source commit outside main's
history, or changed runtime credentials/configuration. If a public-endpoint
check fails after promotion, the helper restores the previous revision while
the failed candidate is still serving. A rollback failure still fails the run;
inspect Cloud Run traffic before retrying. Keep external manual deployments
separate from an active workflow run.

The helper and tests are `scripts/cloud_run_release.py` and
`tests/test_cloud_run_release.py`. Successful reports are attached to the run for
30 days; they contain public procurement evidence, not customer credentials.
The checks do not complete a customer's Google login or test token exchange.
Changes to authentication logic still need a real sign-in test before promotion.

## Google access already configured

| Setting | Value |
| --- | --- |
| Project / region | `workspacealberta-prod` / `northamerica-northeast1` |
| Service | `workspacealberta` |
| Deployment service account | `github-cloud-run@workspacealberta-prod.iam.gserviceaccount.com` |
| Workload Identity provider | `projects/983058968342/locations/global/workloadIdentityPools/github-releases/providers/workspacealberta` |
| Repository variables | `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT` |

GitHub uses short-lived OIDC credentials through Workload Identity Federation.
There is no downloaded service-account key or GCP credential stored in GitHub
Secrets. The provider accepts only repository ID `1112614818`, owner ID
`76745467`, branch `refs/heads/main`, event `workflow_dispatch`, and
`HarleyCoops/WorkspaceAlberta/.github/workflows/deploy-cloud-run.yml@refs/heads/main`.
Renaming the workflow or changing the release branch requires updating that trust.

The deployment account has:

- `roles/run.developer` on the existing `workspacealberta` service.
- `roles/artifactregistry.writer` on the Montréal `cloud-run-source-deploy` repository.
- `roles/iam.serviceAccountUser` on the existing Cloud Run runtime identity,
  `983058968342-compute@developer.gserviceaccount.com`.

The repository's federated principal has `roles/iam.workloadIdentityUser` on
the deployment account. It has no project-wide owner/editor grant or direct
Secret Manager access. The runtime keeps its existing environment and secret
bindings; the workflow does not replace them or change Google callback URLs,
SMTP, ingress, public access, billing, or database schema.

This setup follows Google's [GitHub authentication action](https://github.com/google-github-actions/auth),
[deployment pipeline federation guidance](https://cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines),
and [Cloud Run deployment permissions](https://cloud.google.com/run/docs/deploying).

## Emergency rollback

Use the previous revision recorded in the last successful release summary.
For the September 26 archival-page rollout, that is
`workspacealberta-google-live-faca0c611e08`:

```bash
gcloud run services update-traffic workspacealberta \
  --project workspacealberta-prod --region northamerica-northeast1 \
  --to-revisions=workspacealberta-google-live-faca0c611e08=100
```

This moves traffic without rebuilding or editing credentials. Never substitute
`LATEST` for the exact revision. Re-run the OAuth and procurement verification
scripts against the public endpoint after a manual rollback.

## Initial verification

The stage and promote helper was exercised from the authenticated deployment
machine for the archival-page release. Unit tests cover stale traffic, changed
runtime identity, failed candidate checks, concurrent promotions, successful
promotion, and rollback after a failed production check. Actionlint validates
the workflow. The GitHub-hosted OIDC run can be exercised after this workflow
is merged to main; the trust deliberately rejects feature branches.
