"""Requirement tag library: the single source of truth for every label that is not a model output.

Used by the hosted ``classify_tender`` tool (procurement_core.requirements) and by the research
scripts in ``pipelines/requirement_classifier/``.

Contents:
- ``RESPONSE_TYPES``: the 11 L0 response types (definition shown to the classifier, tool that
  collects it). ``none`` is the catch-all.
- ``SUB_TAGS``: the L1 sub-tags for each response type, plus the reject option.
- routing per canonical tag (answer source, lead time, connector, question);
- ``DOCUMENT_PARTS``: the page-level layer.

Written for Canadian public-sector RFPs in general (construction, professional services,
goods, IT, maintenance), not for one document. Jurisdiction-specific names (COR, WCB) are
given as examples inside generic tags, so an Ontario WSIB letter or an ISO 45001 certificate
lands on the same tag as an Alberta WCB letter or COR.

Every sub-tag set ends with "other_*" and "not_a_bid_requirement":
- the share of "other_*" across a corpus shows where the library needs a new tag;
- "not_a_bid_requirement" lets L1 reject L0 false positives, so L0 can run at high recall.

A canonical tag is "<response_type>.<sub_tag>", e.g. "attach_document.workers_comp".
"""

from __future__ import annotations

# Response type -> (definition shown to the model, tool that collects it).
RESPONSE_TYPES: dict[str, tuple[str, str]] = {
    "none": (
        "The bidder puts nothing in its bid because of this clause: background, definitions, the buyer's "
        "own process, specifications of the work, the printed wording of a form, bond or contract, or any "
        "duty of the contractor after award.",
        "",
    ),
    "attach_document": (
        "Bidder must attach an existing document to its bid: certificate (e.g. COR), licence, proof of "
        "WCB registration, insurance or bonding letter, financial statement, resume, permit. Not documents "
        "the contractor delivers after award (shop drawings, clearance letters before payment).",
        "document_vault",
    ),
    "form_field": (
        "Bidder must fill in a fact about its company on a bid form: legal name, address, business or GST "
        "number, contact person, ownership, years in business.",
        "business_profile",
    ),
    "declaration": (
        "Bidder must sign, certify or acknowledge something as part of its bid: declaration form, conflict "
        "of interest, receipt of addenda, acceptance of terms, authority to bind. Not the signature blocks "
        "of the contract signed after award.",
        "signature_confirmation",
    ),
    "compliance_confirm": (
        "Bidder must state in its bid that it meets a stated requirement (yes/no, comply/does not comply).",
        "compliance_checklist",
    ),
    "narrative": (
        "Bidder must write a description in its proposal: its approach, methodology, work plan, proposed "
        "schedule, quality or safety plan, understanding of the project. Not a specification or schedule "
        "that tells the contractor how to do the work after award.",
        "drafting_interview",
    ),
    "pricing": (
        "Bidder must state prices in its bid: lump sum, unit rates, hourly or labour rates, a fee schedule. "
        "Not definitions of price terms, and not payment procedures after award.",
        "pricing_worksheet",
    ),
    "experience_reference": (
        "Bidder must list in its proposal past projects, client references, key personnel or subcontractors "
        "and their experience.",
        "project_and_people_records",
    ),
    "security_bond": (
        "Bidder must submit bid security with its bid: bid bond, deposit, or a surety's consent or agreement "
        "to bond. Not the printed wording of a bond form, and not bonds the contractor provides after award.",
        "surety_request",
    ),
    "attendance": (
        "Bidder must or may attend a site visit, information meeting or interview before bids close.",
        "calendar",
    ),
    "submission_instruction": (
        "A rule on how, when or where to submit the bid or ask questions: deadline, format, page limit, "
        "file naming, number of copies, question period.",
        "submission_checklist",
    ),
}

NOT_A_REQUIREMENT = (
    "not_a_bid_requirement",
    "On a closer reading the bidder supplies nothing in its bid because of this clause: it is "
    "background, the buyer's process, form wording, or a duty after award.",
)

SUB_TAGS: dict[str, dict[str, str]] = {
    "attach_document": {
        "safety_certification": "Safety program certificate, e.g. COR or SECOR in Alberta, ISO 45001.",
        "workers_comp": "Workers' compensation registration or clearance (WCB, WSIB, WorkSafeBC).",
        "insurance_proof": "Certificate or letter showing insurance coverage.",
        "surety_letter": "Bonding capacity letter or consent of surety.",
        "licence_permit": "Business or trade licence, professional registration, permit.",
        "financial_statements": "Financial statements, bank letter, credit reference.",
        "resumes": "Resumes or CVs of the people proposed.",
        "policy_manual": "An existing quality, safety, environmental or privacy manual or policy.",
        "product_data": "Product data sheets, catalogue pages, samples or specifications of goods offered.",
        "other_document": "Another existing document to attach.",
    },
    "form_field": {
        "legal_name_address": "Legal name, operating name, address.",
        "business_numbers": "GST/HST, business number, corporate registry or vendor number.",
        "contact_person": "Contact person, phone, email.",
        "signatory_authority": "Name and title of the person authorized to sign.",
        "ownership_structure": "Ownership, joint venture or partnership members, parent company.",
        "company_history": "Years in business, size, number of staff, locations.",
        "other_field": "Another company fact on a form.",
    },
    "declaration": {
        "conflict_of_interest": "Declare conflicts of interest or none.",
        "addenda_acknowledgement": "Acknowledge receipt of addenda.",
        "terms_acceptance": "Accept the RFP terms, contract form or limits of liability.",
        "authority_to_bind": "Confirm the signer can bind the bidder; signature and date.",
        "confidentiality": "Sign a non-disclosure or confidentiality undertaking.",
        "legal_compliance": "Certify compliance with laws, sanctions, prohibitions, or no false statements.",
        "other_declaration": "Another signature, certification or acknowledgement.",
    },
    "compliance_confirm": {
        "mandatory_qualification": "Meets a minimum qualification: licence, certification, years, experience.",
        "technical_specification": "Meets a technical specification of the goods or services.",
        "insurance_requirements": "Can meet the stated insurance types and limits.",
        "safety_requirements": "Meets stated safety program requirements.",
        "schedule_delivery": "Can meet the stated schedule, completion date or delivery time.",
        "other_compliance": "Confirms another stated requirement.",
    },
    "narrative": {
        "methodology_approach": "How the bidder will do the work: approach, methodology, means and methods.",
        "project_plan_schedule": "Work plan, proposed schedule, execution plan, work breakdown.",
        "team_organization": "Team structure, roles, organization chart, resourcing.",
        "safety_plan": "Site-specific or project safety plan.",
        "quality_plan": "Quality assurance or quality control plan.",
        "environmental_plan": "Environmental protection, waste or erosion control plan.",
        "risk_management": "Risks, mitigation, contingency.",
        "project_understanding": "Understanding of the project, scope, site or client needs.",
        "community_benefits": "Indigenous participation, local hiring, social or community benefits.",
        "value_innovation": "Value-added services, innovation, alternatives.",
        "other_narrative": "Another written response.",
    },
    "pricing": {
        "lump_sum": "A single fixed or stipulated price.",
        "unit_rates": "Unit prices for quantities or items.",
        "hourly_labour_rates": "Hourly, daily or labour rates by role.",
        "cost_breakdown": "Breakdown of a price by component, phase or line item.",
        "allowances_contingency": "Cash allowances, contingency, provisional sums.",
        "optional_prices": "Alternate, optional or separate prices.",
        "other_pricing": "Another price the bidder must give.",
    },
    "experience_reference": {
        "past_projects": "Descriptions of similar past projects or contracts.",
        "client_references": "Client references with contact details.",
        "key_personnel": "Named key people with qualifications and experience.",
        "subcontractors_suppliers": "List of subcontractors or suppliers and their experience.",
        "other_experience": "Another experience or reference item.",
    },
    "security_bond": {
        "bid_bond": "Bid bond with the bid.",
        "bid_deposit": "Certified cheque, deposit or letter of credit with the bid.",
        "consent_of_surety": "Agreement or consent of surety to provide bonds if awarded.",
        "other_security": "Another form of bid security.",
    },
    "attendance": {
        "mandatory_site_visit": "Site visit that bidders must attend.",
        "optional_site_visit": "Site visit that bidders may attend.",
        "information_session": "Bidders' meeting, briefing or information session.",
        "interview_presentation": "Interview, presentation or demonstration.",
        "other_attendance": "Another event to attend.",
    },
    "submission_instruction": {
        "closing_deadline": "Closing date and time, or where and when bids are due.",
        "question_period": "Deadline or method for questions and clarifications.",
        "format_page_limits": "Format, structure, page limits, font, order of sections.",
        "file_packaging": "File naming, number of files, separate technical and price packages.",
        "delivery_method": "Submission portal, email or physical delivery.",
        "other_instruction": "Another submission rule.",
    },
}

# Routing questions asked for every gated unit, whatever its type.
ANSWER_SOURCE = {
    "company_profile": "A stable company fact, stored once and reused in every bid.",
    "document_on_file": "An existing document the company already holds.",
    "person_input": "Someone at the company must write or decide something specific to this bid.",
    "calculation": "Numbers worked out for this bid: prices, quantities, schedule.",
    "third_party": "Must come from outside the company: surety, insurer, references, suppliers, subcontractors.",
    "calendar_action": "A date or event to put in the calendar and act on.",
}

LEAD_TIME = {
    "minutes": "Can be answered from stored information or in a few minutes.",
    "days": "Needs work or a reply within a few days.",
    "weeks": "Needs a week or more: third-party documents, plans, quotes, approvals.",
}


def sub_tag_options(response_type: str) -> dict[str, str]:
    options = dict(SUB_TAGS.get(response_type, {}))
    options[NOT_A_REQUIREMENT[0]] = NOT_A_REQUIREMENT[1]
    return options


# ---------------------------------------------------------------------------------------------
# Routing: fixed per tag, not asked per clause. Who answers and how long it takes depend on what
# kind of requirement it is, so they live here. A firm can override these per tenant later
# (e.g. lead time for safety_certification is "minutes" if the COR is on file, months if not).
# Each entry: (answer_source, lead_time, connector)

TYPE_ROUTING: dict[str, tuple[str, str, str]] = {
    "attach_document": ("document_on_file", "minutes", "document_vault"),
    "form_field": ("company_profile", "minutes", "business_profile"),
    "declaration": ("person_input", "minutes", "signature_confirmation"),
    "compliance_confirm": ("person_input", "minutes", "compliance_checklist"),
    "narrative": ("person_input", "weeks", "drafting_interview"),
    "pricing": ("calculation", "weeks", "pricing_worksheet"),
    "experience_reference": ("document_on_file", "days", "project_and_people_records"),
    "security_bond": ("third_party", "weeks", "surety_request"),
    "attendance": ("calendar_action", "minutes", "calendar"),
    "submission_instruction": ("calendar_action", "minutes", "submission_checklist"),
}

TAG_ROUTING: dict[str, tuple[str, str, str]] = {
    "attach_document.surety_letter": ("third_party", "weeks", "surety_request"),
    "attach_document.insurance_proof": ("third_party", "days", "insurer_request"),
    "attach_document.workers_comp": ("third_party", "days", "document_vault"),
    "attach_document.product_data": ("third_party", "days", "supplier_request"),
    "attach_document.resumes": ("document_on_file", "days", "project_and_people_records"),
    "declaration.conflict_of_interest": ("person_input", "days", "signature_confirmation"),
    "compliance_confirm.insurance_requirements": ("third_party", "days", "insurer_request"),
    "compliance_confirm.mandatory_qualification": ("document_on_file", "minutes", "compliance_checklist"),
    "narrative.project_understanding": ("person_input", "days", "drafting_interview"),
    "narrative.team_organization": ("person_input", "days", "drafting_interview"),
    "narrative.value_innovation": ("person_input", "days", "drafting_interview"),
    "pricing.hourly_labour_rates": ("calculation", "days", "pricing_worksheet"),
    "pricing.allowances_contingency": ("calculation", "minutes", "pricing_worksheet"),
    "experience_reference.client_references": ("third_party", "days", "project_and_people_records"),
    "experience_reference.key_personnel": ("person_input", "days", "project_and_people_records"),
    "experience_reference.subcontractors_suppliers": ("third_party", "weeks", "supplier_request"),
    "submission_instruction.closing_deadline": ("calendar_action", "minutes", "calendar"),
    "submission_instruction.question_period": ("calendar_action", "minutes", "calendar"),
}


def routing(tag: str) -> dict[str, str]:
    rtype, _, sub = tag.partition(".")
    source, lead, connector = TAG_ROUTING.get(tag) or TYPE_ROUTING.get(rtype, ("person_input", "days", "drafting_interview"))
    return {
        "answer_source": source,
        "lead_time": lead,
        "connector": connector,
        "question": SUB_TAGS.get(rtype, {}).get(sub, sub.replace("_", " ")),
    }


# ---------------------------------------------------------------------------------------------
# Page-level layer: which part of the tender package a page belongs to.

DOCUMENT_PARTS = {
    "cover_or_contents": "Cover page, notice, key dates, table of contents.",
    "bid_instructions": "Instructions to bidders: the procurement process, how to submit, evaluation criteria.",
    "bid_forms": "A form or schedule the bidder fills in, signs and submits with its bid: submission, "
                 "price, declaration, experience or personnel forms.",
    "contract_terms": "The agreement or general and supplementary conditions of the contract.",
    "contract_schedule": "A schedule or appendix of the contract: insurance, bonds, payment, changes, "
                         "acceptance, disputes, site rules, execution plans.",
    "specifications": "Technical specifications of the work, goods or services (divisions, sections).",
    "drawings": "Drawings, drawing lists, title blocks.",
    "reference_report": "A background report or appendix provided for information, e.g. an assessment or test results.",
}
BID_PARTS = {"cover_or_contents", "bid_instructions", "bid_forms"}
