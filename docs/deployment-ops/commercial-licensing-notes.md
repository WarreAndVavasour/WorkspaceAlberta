# Commercial Licensing Notes: Hermes Agent and Cohere

This is a practical licensing and terms summary for WorkspaceAlberta. It is not legal advice. Have counsel review the exact product architecture, customer contracts, data flows, model usage, and vendor agreements before launch.

## Product context

WorkspaceAlberta is a commercial leased AI workspace subscription. The customer receives a deployed terminal and ongoing service, but does not own the equipment. The service may use Hermes Agent, Cohere APIs/models, local tools, MCP servers, and customer-specific workflows.

## Hermes Agent

Links:

- Repository: https://github.com/NousResearch/hermes-agent
- License: https://github.com/NousResearch/hermes-agent/blob/main/LICENSE
- Docs: https://hermes-agent.nousresearch.com/docs/

Finding:

Hermes Agent is licensed under the MIT License.

MIT generally permits commercial use, copying, modification, distribution, sublicensing, and sale of copies of the software, provided the copyright notice and permission notice are preserved in copies or substantial portions of the software.

Practical conclusion:

Commercial deployment of tools built with Hermes Agent appears permitted by the Hermes Agent software license, as long as WorkspaceAlberta preserves required MIT notices.

Important caveat:

The MIT license covers the Hermes Agent code. It does not grant rights to third-party models, APIs, plugins, MCP servers, hosted services, datasets, or proprietary components used with Hermes.

## Cohere API / SaaS

Links:

- Terms of Use: https://cohere.com/terms-of-use
- Platform docs: https://docs.cohere.com/docs/the-cohere-platform
- Models docs: https://docs.cohere.com/docs/models
- Going live / production key: https://docs.cohere.com/docs/going-live
- Rate limits / API keys: https://docs.cohere.com/docs/rate-limits
- Usage Policy: https://docs.cohere.com/docs/usage-policy
- Enterprise Data Commitments: https://cohere.com/enterprise-data-commitments
- Privacy Policy: https://cohere.com/privacy

Finding:

Cohere’s docs explicitly contemplate developers and enterprises building production applications with Cohere models. Cohere has trial keys and production keys, and its “Going Live” docs describe moving to a production key if you want to serve Cohere in production.

Practical conclusion:

Using Cohere API inside WorkspaceAlberta application features appears commercially plausible, subject to Cohere’s terms, usage policy, production key/subscription, rate limits, safety review where applicable, and any enterprise agreement.

## The main Cohere risk: resale / service bureau / timesharing

Cohere’s terms include restrictions against using, copying, distributing, making available, or commercially exploiting the Cohere Solution in ways that may resemble timesharing, service bureau use, resale, or sublicensing without permission.

This matters for WorkspaceAlberta.

Lower-risk framing:

- WorkspaceAlberta is an application/service that uses Cohere in the backend.
- Customers buy WorkspaceAlberta workflows, procurement intelligence, onboarding, and support.
- Customers do not get raw Cohere API access.
- Cohere is one model provider inside the WorkspaceAlberta service.

Higher-risk framing:

- WorkspaceAlberta is effectively reselling general Cohere model/API access.
- Customers can use WorkspaceAlberta as a generic Cohere terminal.
- One Cohere API key is pooled across unrelated customers without appropriate agreement.
- Customers are sublicensed access to Cohere itself.

Recommendation:

Before launch, ask Cohere or counsel whether the WorkspaceAlberta leased workspace subscription is covered by standard Cohere API terms or needs a negotiated commercial/enterprise agreement.

## Cohere open-weight models

Do not assume Cohere open weights can be commercially deployed.

Representative CohereForAI models on Hugging Face have used CC BY-NC 4.0-style non-commercial licenses. That means self-hosting those weights commercially may not be allowed without a separate commercial license from Cohere.

Practical rule:

- Cohere API/SaaS production key: commercial use may be allowed under Cohere terms.
- Cohere open weights: check each model license. If it is non-commercial, do not use it commercially without separate permission.

## Usage policy considerations

Cohere’s Usage Policy restricts or prohibits certain use cases. WorkspaceAlberta should review features carefully, especially if the service touches:

- employment decisions
- finance or insurance
- housing
- healthcare
- education
- law enforcement
- legal advice or legal determinations
- government benefits or essential services
- identity verification
- surveillance
- political persuasion
- minors
- weapons, controlled substances, or illegal activity

Back-office uses like document summarization, transcription, search, and internal knowledge agents are generally lower-risk, but still need responsible design and customer terms.

If WorkspaceAlberta exposes public-facing or customer-facing AI agents, disclose that users are interacting with AI.

## Data and privacy notes

Confirm before production:

- Whether prompts and generations are retained.
- Whether prompts/generations are used for model training.
- Whether WorkspaceAlberta can opt out of training use.
- Whether a DPA is needed.
- Whether customers require PIPEDA, FOIP, PHIPA, SOC 2, data residency, or private deployment commitments.
- Whether tender documents, business profiles, or bid-room files contain confidential or personal information.

Cohere Enterprise Data Commitments should be reviewed for retention, training, and deployment options.

## Recommended compliance questions

Ask Cohere, counsel, or both:

1. Is WorkspaceAlberta an application using Cohere, or does it risk being characterized as service bureau/timesharing/resale of Cohere?
2. Can one WorkspaceAlberta production key serve multiple commercial customers, or should customers have separate keys/accounts?
3. Do standard Cohere terms allow multi-tenant SaaS embedding Cohere outputs into a leased hardware/software workspace?
4. Are any planned WorkspaceAlberta features high-risk under Cohere’s Usage Policy?
5. Do any workflows require AI disclosure to end users?
6. Will minors use any part of the service?
7. Are we using Cohere API only, or any self-hosted Cohere open weights?
8. If self-hosting, do we have a commercial model license?
9. What customer data is sent to Cohere, retained, or used for training?
10. Do we need a DPA, SOC 2/security packet, regional data commitments, or enterprise agreement?
11. What OSS notice process will preserve Hermes Agent MIT notices and dependency notices?

## Practical recommendation

Hermes Agent is fine to build on commercially under MIT, with notice preservation.

Cohere API is likely usable commercially as an embedded model provider, but WorkspaceAlberta should not present itself as reselling Cohere access. The safe product story is:

WorkspaceAlberta sells a managed AI workspace, procurement workflows, setup, training, support, and custom integrations. Cohere is a backend model provider used to deliver those features.

Do not self-host Cohere open-weight models commercially unless the exact model license permits commercial use or Cohere grants a commercial license.
